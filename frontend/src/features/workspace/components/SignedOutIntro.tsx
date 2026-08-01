/**
 * The signed-out home screen: what GrandMate is, how it helps, and who it is for.
 *
 * This is the only view a visitor sees before logging in, so it carries the whole
 * explanation of the product. Copy is deliberately held to what the system actually
 * does — engine-computed move quality, cross-game aggregation, persona framing — rather
 * than what a landing page would like to claim. An overstated promise here is a support
 * burden later, and the "explanation, never invention" boundary in card one is the
 * project's central architectural rule (deterministic analysis stays separate from LLM
 * explanation), not marketing copy.
 */
import { Cpu, TrendingUp, Users } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';

interface IntroCard {
  icon: LucideIcon;
  title: string;
  /** Answers one of: what is it, how does it help, who is it for. */
  question: string;
  body: string;
}

const INTRO_CARDS: IntroCard[] = [
  {
    icon: Cpu,
    title: 'Analysis you can trust',
    question: 'What it is',
    body:
      'Import your games from Lichess, Chess.com, or a PGN file. Every move is evaluated by ' +
      'Stockfish, so move quality is computed rather than guessed. The coaching layer explains ' +
      'that analysis — it never invents the chess.',
  },
  {
    icon: TrendingUp,
    title: 'Patterns, not just blunders',
    question: 'How it helps',
    body:
      'One bad move is an accident. The same bad move across thirty games is a habit. GrandMate ' +
      'looks across your games to find the weaknesses that keep recurring and the openings that ' +
      'cost you most, then turns them into a training plan you can ask questions about.',
  },
  {
    icon: Users,
    title: 'Built for how you learn',
    question: 'Who it is for',
    body:
      'Players reviewing their own games, coaches preparing for a lesson, and kids who need it ' +
      'explained without the jargon. The same underlying analysis, framed at the depth and tone ' +
      'that suits the reader.',
  },
];

export function SignedOutIntro() {
  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle>GrandMate</CardTitle>
          <CardDescription>
            Log in with Lichess or Chess.com to import games, see analysis, and chat about your
            play.
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Single column on phones, three across from `md` up: the body copy needs the width
          to stay readable, so these do not go side by side on small screens. */}
      <div className="grid gap-4 md:grid-cols-3">
        {INTRO_CARDS.map(({ icon: Icon, title, question, body }) => (
          <Card key={title} className="flex flex-col">
            <CardHeader>
              <Icon className="mb-2 h-5 w-5 text-muted-foreground" aria-hidden="true" />
              <CardDescription className="text-xs font-medium uppercase tracking-wide">
                {question}
              </CardDescription>
              <CardTitle>{title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{body}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
