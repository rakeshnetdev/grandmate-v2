# Playbook — Backup and Recovery

This playbook outlines the procedures for backing up and restoring the GrandMate database and local file storage in production (Fly.io/Vercel or equivalent).

---

## 1. Relational Database & Vector Store

GrandMate uses a single Postgres database with the `pgvector` extension for both relational tables (Users, Profiles, Games, Jobs, Reports, Memory) and vector embeddings (LangGraph checkpoint and store tables).

### Backup Procedure

To back up the production database, perform a schema-and-data dump. If hosting on Fly.io Postgres or a managed Postgres instance (like Supabase or Neon):

1. **Get Connection Details**: Extract the `DATABASE_URL` from the application environment variables:
   ```bash
   fly secrets list
   # Or get the connection string directly:
   fly config env | grep DATABASE_URL
   ```
2. **Execute pg_dump**: Run a compressed custom-format dump (`-Fc`) using `pg_dump`. This format is highly compressed and allows selective restore of objects:
   ```bash
   pg_dump -Fc -d "postgresql://user:password@host:port/database" -f grandmate_db_backup_$(date +%F).dump
   ```
   *Note: Ensure the local machine running `pg_dump` has matching/compatible Postgres client utilities (v17 is recommended).*

### Recovery Procedure

1. **Create Target Database**: Ensure a fresh, empty Postgres database is running.
2. **Enable pgvector Extension**: Connect to the database as superuser and execute:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. **Run pg_restore**: Restore the custom dump file into the new database:
   ```bash
   pg_restore --clean --no-owner --no-privileges -d "postgresql://user:password@host:port/database" grandmate_db_backup_YYYY-MM-DD.dump
   ```
4. **Run Alembic Migrations**: Bring the database state to the latest migration head:
   ```bash
   uv run alembic upgrade head
   ```

---

## 2. Ephemeral/Persistent File Storage

GrandMate writes uploaded PGNs and generated reports to `/app/.storage` on the local container filesystem. In production, this directory is backed by a persistent Fly.io Volume (`grandmate_storage` mounted at `/app/.storage`).

### Backup Procedure

To back up the persistent volume, you can copy files out of the running container or create a tarball of the persistent directory.

1. **Verify Volume Mount**: Check the running machine for the storage directory:
   ```bash
   fly ssh console -C "ls -la /app/.storage"
   ```
2. **Archive the Volume**: Create a compressed tarball of the `.storage` directory inside the container and stream it to your local machine:
   ```bash
   fly ssh console -C "tar -czf - -C /app .storage" > grandmate_storage_backup_$(date +%F).tar.gz
   ```
3. **(Alternative) Sync to S3/R2**: If an S3/R2 storage adapter is configured, use standard bucket replication rules on your cloud provider.

### Recovery Procedure

1. **Spin up target Machine**: Ensure the Fly.io machine with the volume mount is running.
2. **Restore Archive**: Stream the local backup tarball back to the container and extract it:
   ```bash
   cat grandmate_storage_backup_YYYY-MM-DD.tar.gz | fly ssh console -C "tar -xzf - -C /app"
   ```
3. **Verify File Permissions**: Confirm that the extracted files are owned by the `grandmate` user (UID/GID 10001) so the application can read and write to them:
   ```bash
   fly ssh console -C "chown -R 10001:10001 /app/.storage"
   ```

---

## 3. LangGraph Checkpoint & Store Recovery

LangGraph state is stored in Postgres. If the database was restored using the steps above, the checkpoints are also restored. If you need to debug or clear graph checkpointer states without destroying the main application tables:

1. **Trashing LangGraph Tables**: You can safely drop the checkpointer tables if they become corrupted or out of sync. LangGraph will automatically recreate them at boot.
   ```sql
   DROP TABLE IF EXISTS checkpoint_writes;
   DROP TABLE IF EXISTS checkpoints;
   DROP TABLE IF EXISTS checkpoint_blobs;
   DROP TABLE IF EXISTS store;
   ```
2. **Verification**: Restart the backend container. The lifespan startup flow or first connection compiles the graph factories and recreates the tables.

---

## 4. Ingestion Corpus Reconstruction

If the database is restored but the vector storage for the knowledge base is empty (e.g., `search_knowledge` returns no records), you must re-run the one-shot ingestion script to populate the embeddings:

1. **Run Ingest Script**: Run the corpus ingestion command within the production container context:
   ```bash
   fly ssh console -C "uv run python -m scripts.ingest_corpus"
   ```
2. **Verify Embeddings Count**: Check that chunk collections were successfully inserted into the database.
