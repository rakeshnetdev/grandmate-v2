/**
 * PGN upload form: paste text, choose one or more files, or both together.
 *
 * A single submit always goes through the same `useCreateImport` call — there is no
 * separate "batch mode" toggle. A file containing several concatenated games (a typical
 * Lichess/Chess.com export) is parsed into that many games server-side without the user
 * doing anything different from uploading a single-game file.
 */
import { useRef, useState } from 'react';

import { Button } from '@/shared/components/ui/button';
import { Textarea } from '@/shared/components/ui/textarea';
import { ApiError } from '@/shared/lib/api-client';

import type { JobSummary } from '../api/imports';
import { useCreateImport } from '../hooks/useImports';

function describeUploadError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) {
      const detail = (error.body as { detail?: string } | undefined)?.detail;
      return detail ?? 'That submission could not be processed.';
    }
    if (error.status === 413) {
      const detail = (error.body as { detail?: string } | undefined)?.detail;
      return detail ?? 'One of the files is too large.';
    }
  }
  return 'Something went wrong. Please try again.';
}

interface UploadFormProps {
  onImported?: (job: JobSummary) => void;
}

export function UploadForm({ onImported }: UploadFormProps) {
  const [pgnText, setPgnText] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const createImport = useCreateImport();

  const hasSubmittableContent = pgnText.trim().length > 0 || files.length > 0;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!hasSubmittableContent) {
      return;
    }
    createImport.mutate(
      { pgnText, files },
      {
        onSuccess: (job) => {
          setPgnText('');
          setFiles([]);
          if (fileInputRef.current) {
            fileInputRef.current.value = '';
          }
          onImported?.(job);
        },
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-1">
        <label htmlFor="pgn-text" className="text-sm font-medium">
          Paste PGN
        </label>
        <Textarea
          id="pgn-text"
          value={pgnText}
          onChange={(event) => setPgnText(event.target.value)}
          placeholder='[Event "..."]&#10;[White "..."]&#10;...&#10;1. e4 e5 ...'
          disabled={createImport.isPending}
          rows={8}
        />
      </div>

      <div className="space-y-1">
        <label htmlFor="pgn-files" className="text-sm font-medium">
          Or upload PGN file(s)
        </label>
        <input
          id="pgn-files"
          ref={fileInputRef}
          type="file"
          accept=".pgn,text/plain"
          multiple
          onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          disabled={createImport.isPending}
          className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border file:border-input file:bg-background file:px-3 file:py-1 file:text-sm file:font-medium"
        />
        {files.length > 0 && (
          <p className="text-xs text-muted-foreground">
            {files.length} file{files.length === 1 ? '' : 's'} selected:{' '}
            {files.map((f) => f.name).join(', ')}
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          A file may contain one game or many concatenated games — both are handled the same way.
        </p>
      </div>

      {createImport.isError && (
        <p className="text-sm text-destructive">{describeUploadError(createImport.error)}</p>
      )}

      <Button type="submit" disabled={createImport.isPending || !hasSubmittableContent}>
        {createImport.isPending ? 'Importing…' : 'Import games'}
      </Button>
    </form>
  );
}
