"""PGN parsing/validation unit tests. No database needed — pure functions."""

from __future__ import annotations

from app.domain.imports.parsing import RejectionReason, parse_pgn_text

VALID_GAME = """[Event "Test"]
[Site "?"]
[Date "2026.01.01"]
[Round "1"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0
"""

OTHER_VALID_GAME = """[Event "Test"]
[Site "?"]
[Date "2026.01.02"]
[Round "1"]
[White "Carol"]
[Black "Dave"]
[Result "0-1"]

1. d4 d5 2. c4 e6 0-1
"""


class TestValidGames:
    def test_parses_a_single_game(self) -> None:
        result = parse_pgn_text(VALID_GAME)

        assert len(result.parsed) == 1
        assert result.rejected == []
        game = result.parsed[0]
        assert game.headers["White"] == "Alice"
        assert game.headers["Black"] == "Bob"
        assert game.moves_uci == ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]

    def test_parses_multiple_concatenated_games_in_one_file(self) -> None:
        """The core requirement: a batch is not a special case, it's N games in one text."""
        result = parse_pgn_text(VALID_GAME + "\n" + OTHER_VALID_GAME)

        assert len(result.parsed) == 2
        assert result.rejected == []
        assert {g.headers["White"] for g in result.parsed} == {"Alice", "Carol"}

    def test_content_hash_is_stable_across_identical_games(self) -> None:
        first = parse_pgn_text(VALID_GAME).parsed[0]
        second = parse_pgn_text(VALID_GAME).parsed[0]

        assert first.content_hash == second.content_hash

    def test_each_games_pgn_text_is_scoped_to_itself_not_the_whole_batch(self) -> None:
        """Regression: storing the whole source text under every game's key left every
        game in a multi-game file pointing at the same blob, with no way to tell which
        game was which. Each `ParsedGame.pgn_text` must contain only its own game."""
        result = parse_pgn_text(VALID_GAME + "\n" + OTHER_VALID_GAME)

        alice_game = next(g for g in result.parsed if g.headers["White"] == "Alice")
        carol_game = next(g for g in result.parsed if g.headers["White"] == "Carol")

        assert "Carol" not in alice_game.pgn_text
        assert "Alice" not in carol_game.pgn_text
        assert "Bb5" in alice_game.pgn_text
        assert "c4" in carol_game.pgn_text

    def test_pgn_text_round_trips_through_the_parser(self) -> None:
        parsed = parse_pgn_text(VALID_GAME).parsed[0]

        reparsed = parse_pgn_text(parsed.pgn_text).parsed[0]

        assert reparsed.moves_uci == parsed.moves_uci
        assert reparsed.content_hash == parsed.content_hash

    def test_content_hash_ignores_comments_and_clock_annotations(self) -> None:
        """Same moves, same result, same players — must hash identically even when a
        different export tool adds commentary."""
        annotated = VALID_GAME.replace(
            "1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0",
            "1. e4 {Good move} e5 2. Nf3 {clk 0:05:00} Nc6 3. Bb5 1-0",
        )

        plain_hash = parse_pgn_text(VALID_GAME).parsed[0].content_hash
        annotated_hash = parse_pgn_text(annotated).parsed[0].content_hash

        assert plain_hash == annotated_hash

    def test_content_hash_differs_for_different_games(self) -> None:
        first = parse_pgn_text(VALID_GAME).parsed[0]
        second = parse_pgn_text(OTHER_VALID_GAME).parsed[0]

        assert first.content_hash != second.content_hash


class TestMalformedGames:
    def test_rejects_garbage_text(self) -> None:
        result = parse_pgn_text("this is not a pgn file at all")

        assert result.parsed == []
        assert len(result.rejected) == 1
        assert result.rejected[0].reason in (
            RejectionReason.MALFORMED_PGN,
            RejectionReason.MISSING_REQUIRED_TAG,
            RejectionReason.NO_MOVES,
        )

    def test_rejects_empty_text(self) -> None:
        result = parse_pgn_text("")

        assert result.parsed == []
        assert len(result.rejected) == 1
        assert result.rejected[0].reason == RejectionReason.MALFORMED_PGN

    def test_rejects_a_game_with_an_illegal_move(self) -> None:
        illegal = VALID_GAME.replace("3. Bb5 1-0", "3. Qxd8 1-0")

        result = parse_pgn_text(illegal)

        assert result.parsed == []
        assert result.rejected[0].reason == RejectionReason.MALFORMED_PGN

    def test_rejects_a_game_missing_player_tags(self) -> None:
        no_players = VALID_GAME.replace('[White "Alice"]', "").replace('[Black "Bob"]', "")

        result = parse_pgn_text(no_players)

        assert result.parsed == []
        assert result.rejected[0].reason == RejectionReason.MISSING_REQUIRED_TAG

    def test_rejects_a_game_with_no_moves(self) -> None:
        no_moves = VALID_GAME.replace("1. e4 e5 2. Nf3 Nc6 3. Bb5 1-0", "1-0")

        result = parse_pgn_text(no_moves)

        assert result.parsed == []
        assert result.rejected[0].reason == RejectionReason.NO_MOVES

    def test_one_bad_game_does_not_stop_the_rest_of_the_batch(self) -> None:
        """A malformed game in a multi-game file must not sink the whole batch."""
        illegal = VALID_GAME.replace("3. Bb5 1-0", "3. Qxd8 1-0")
        batch = illegal + "\n" + OTHER_VALID_GAME

        result = parse_pgn_text(batch)

        assert len(result.parsed) == 1
        assert result.parsed[0].headers["White"] == "Carol"
        assert len(result.rejected) == 1
        assert result.rejected[0].reason == RejectionReason.MALFORMED_PGN


class TestVariantGames:
    """Non-standard variants must never enter the pipeline.

    Their positions are illegal under standard rules and segfault Stockfish downstream
    (an Antichess game legally captures both kings), so rejection happens at ingestion.
    """

    def test_rejects_an_antichess_game(self) -> None:
        # Real Antichess: Black's king is captured on move 7, leaving a kingless position
        # that standard Stockfish crashes on rather than refusing.
        antichess = """[Event "Casual Antichess game"]
[Site "https://lichess.org/xxxxxxxx"]
[Date "2026.01.01"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]
[Variant "Antichess"]

1. e3 b6 2. Bb5 Bb7 3. Bxd7 Bxg2 4. Bxe8 Bxh1 1-0
"""

        result = parse_pgn_text(antichess)

        assert result.parsed == []
        assert result.rejected[0].reason == RejectionReason.UNSUPPORTED_VARIANT
        assert "Antichess" in result.rejected[0].detail

    def test_rejects_other_non_standard_variants(self) -> None:
        for variant in ("Atomic", "Crazyhouse", "King of the Hill", "Three-check"):
            tagged = VALID_GAME.replace('[Round "1"]', f'[Variant "{variant}"]')

            result = parse_pgn_text(tagged)

            assert result.parsed == [], variant
            assert result.rejected[0].reason == RejectionReason.UNSUPPORTED_VARIANT, variant

    def test_accepts_standard_variant_tags(self) -> None:
        """`Standard`, `From Position`, and `Chess960` all play by standard rules."""
        for variant in ("Standard", "From Position", "Chess960"):
            tagged = VALID_GAME.replace('[Round "1"]', f'[Variant "{variant}"]')

            result = parse_pgn_text(tagged)

            assert len(result.parsed) == 1, variant
            assert result.rejected == [], variant

    def test_rejects_an_unrecognised_variant_tag(self) -> None:
        tagged = VALID_GAME.replace('[Round "1"]', '[Variant "Definitely Not A Variant"]')

        result = parse_pgn_text(tagged)

        assert result.parsed == []
        assert result.rejected[0].reason == RejectionReason.UNSUPPORTED_VARIANT

    def test_a_variant_game_does_not_sink_the_rest_of_the_batch(self) -> None:
        """A Lichess export mixes variants into one file — the standard games still land."""
        variant_game = VALID_GAME.replace('[Round "1"]', '[Variant "Antichess"]')
        batch = variant_game + "\n" + OTHER_VALID_GAME

        result = parse_pgn_text(batch)

        assert len(result.parsed) == 1
        assert result.parsed[0].headers["White"] == "Carol"
        assert result.rejected[0].reason == RejectionReason.UNSUPPORTED_VARIANT


class TestLargeBatch:
    def test_parses_a_fifty_game_batch(self) -> None:
        batch = "\n".join([VALID_GAME, OTHER_VALID_GAME] * 25)

        result = parse_pgn_text(batch)

        assert len(result.parsed) == 50
        assert result.rejected == []
