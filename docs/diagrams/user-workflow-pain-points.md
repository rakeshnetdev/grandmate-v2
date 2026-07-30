# Current-state workflow and its pain points

Referenced from [`Deliverables.md` §1.3](../Deliverables.md#13-current-state-workflow-and-bottlenecks).

How a club player tries to learn from their games today, without GrandMate. Red nodes are
the points where the loop fails to produce a lesson.

```mermaid
flowchart LR
    A["Finish a game online"] --> B["Open the platform's<br/>computer analysis"]
    B --> C["Click through the<br/>evaluation bar, move by move"]
    C --> D{"Understand *why*<br/>the move was bad?"}

    D -- No --> E["See a centipawn number<br/>(-2.4 at move 23)"]
    E --> F["Google the opening ·<br/>ask a Discord ·<br/>guess"]
    F --> G{"A lesson specific<br/>to *my* play?"}

    G -- "Almost never" --> H["No way to tell a one-off<br/>blunder from a habit"]
    G -- No --> I["Give up, move on"]
    D -- Sometimes --> H

    H --> J["Play the next game —<br/>repeat the same mistake"]
    I --> J
    J --> A

    classDef pain fill:#ffe0e0,stroke:#d33,color:#900;
    class C,E,F,H,I pain
```

## What the diagram is arguing

The failure is not that engine output is *wrong* — it is exact. The failure is that it is
**per-game and per-move by construction**, so it can never answer the question the player
actually has: *which of my mistakes are habits, and what do I drill?*

The three red nodes in the middle are where the alternatives break down too. Clicking an
evaluation bar is manual pattern-matching the player is least equipped to do about their
own blind spots. Googling produces general advice, not advice about *this* player. And
nothing in the loop retains anything, so the next game starts from zero.

A human coach breaks the loop — but at $30–100/hour, reviewing perhaps one game per
session, that scales to neither thirty games nor a coach's dozen students.
