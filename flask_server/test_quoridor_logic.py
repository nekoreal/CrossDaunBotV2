import unittest

from flask_server.quoridor_logic import BOARD_SIZE, CENTER, QuoridorGame, Wall


def make_game():
    return QuoridorGame([
        {"tg_id": index, "username": f"player{index}"}
        for index in range(4)
    ], now=100)


class QuoridorGameTests(unittest.TestCase):
    def test_game_requires_four_players_and_starts_around_board(self):
        game = make_game()
        self.assertEqual(BOARD_SIZE, 11)
        self.assertEqual(CENTER, (5, 5))
        self.assertEqual([(pawn.row, pawn.col) for pawn in game.players], [
            (0, 5), (5, 10), (10, 5), (5, 0)
        ])
        with self.assertRaises(ValueError):
            QuoridorGame([{"tg_id": 1, "username": "solo"}])

    def test_can_jump_a_chain_of_three_players(self):
        game = make_game()
        game.players[0].row, game.players[0].col = 4, 1
        game.players[1].row, game.players[1].col = 4, 2
        game.players[2].row, game.players[2].col = 4, 3
        game.players[3].row, game.players[3].col = 4, 4
        self.assertIn((4, 5), game.legal_moves(0))

    def test_wall_behind_a_chain_allows_diagonal_jump(self):
        game = make_game()
        game.players[0].row, game.players[0].col = 4, 0
        game.players[1].row, game.players[1].col = 4, 1
        game.players[2].row, game.players[2].col = 4, 2
        game.players[3].row, game.players[3].col = 4, 3
        game.walls.append(Wall(4, 3, "vertical"))
        self.assertNotIn((4, 4), game.legal_moves(0))
        self.assertIn((3, 3), game.legal_moves(0))
        self.assertIn((5, 3), game.legal_moves(0))

    def test_wall_must_leave_every_player_a_path_to_center(self):
        game = make_game()
        game.players[0].row, game.players[0].col = 5, 4
        game.walls = [
            Wall(4, 2, "vertical"),
            Wall(3, 3, "horizontal"),
            Wall(5, 3, "horizontal"),
        ]
        self.assertTrue(all(game._has_path_to_center(index) for index in range(4)))
        before = len(game.walls)
        self.assertFalse(game.place_wall(0, 4, 4, "vertical"))
        self.assertEqual(len(game.walls), before)
        self.assertEqual(game.players[0].walls, 5)

    def test_legal_wall_uses_one_turn_and_blocks_both_edges(self):
        game = make_game()
        self.assertTrue(game.place_wall(0, 0, 4, "horizontal"))
        self.assertEqual(game.players[0].walls, 4)
        self.assertEqual(game.current_turn, 1)
        self.assertNotIn((1, 4), game.legal_moves(0))

    def test_walls_cannot_cross_at_the_same_anchor(self):
        game = make_game()
        game.walls.append(Wall(0, 4, "horizontal"))
        game.current_turn = 1
        self.assertFalse(game.place_wall(1, 0, 4, "vertical"))
        self.assertEqual(len(game.walls), 1)
        self.assertEqual(game.players[1].walls, 5)

    def test_parallel_walls_cannot_overlap(self):
        game = make_game()
        game.walls.append(Wall(0, 4, "horizontal"))
        game.current_turn = 1
        self.assertFalse(game.place_wall(1, 0, 5, "horizontal"))
        self.assertEqual(len(game.walls), 1)

    def test_turn_timeout_move_uses_shortest_available_step(self):
        game = make_game()
        self.assertEqual(game.shortest_move(0), (1, 5))
        self.assertEqual(game.auto_move(), (1, 5))
        self.assertEqual(game.current_turn, 1)

    def test_shortest_move_routes_around_a_wall(self):
        game = make_game()
        game.walls.append(Wall(0, 4, "horizontal"))
        self.assertEqual(game.shortest_move(0), (0, 6))

    def test_only_the_player_whose_turn_it_is_can_move(self):
        game = make_game()
        self.assertFalse(game.move(1, 4, 9))
        self.assertTrue(game.move(0, 1, 5))

    def test_reaching_the_center_wins(self):
        game = make_game()
        game.players[0].row, game.players[0].col = 4, 5
        self.assertTrue(game.move(0, *CENTER))
        self.assertIsNone(game.winner)
        self.assertFalse(game.finished)
        self.assertEqual(game.players[0].place, 1)
        self.assertEqual(game.current_turn, 1)

    def test_third_player_to_reach_center_gets_last_player_assigned_fourth(self):
        game = make_game()
        for player_index in range(3):
            game.current_turn = player_index
            pawn = game.players[player_index]
            pawn.row, pawn.col = (4, 5) if player_index == 0 else (
                ((4, 5), (5, 6), (6, 5))[player_index]
            )
            self.assertTrue(game.move(player_index, *CENTER))

        self.assertTrue(game.finished)
        self.assertEqual([pawn.place for pawn in game.players], [1, 2, 3, 4])
        self.assertEqual(game.winner, 0)

    def test_surrender_hides_player_keeps_walls_and_preserves_four_places(self):
        game = make_game()
        game.walls.append(Wall(1, 1, "horizontal"))
        self.assertTrue(game.surrender(0))
        self.assertFalse(game.players[0].active)
        self.assertTrue(game.players[0].surrendered)
        self.assertEqual(game.players[0].place, 4)
        self.assertEqual(game.walls, [Wall(1, 1, "horizontal")])
        self.assertEqual(game.players[0].place, 4)

        game.current_turn = 1
        game.players[1].row, game.players[1].col = 4, 5
        game.players[2].row, game.players[2].col = 5, 6
        for player_index in (1, 2):
            self.assertTrue(game.move(player_index, *CENTER))
            if not game.finished:
                game.current_turn = 2
        self.assertTrue(game.finished)
        self.assertEqual(sorted(pawn.place for pawn in game.players), [1, 2, 3, 4])

    def test_four_consecutive_automatic_moves_cause_surrender(self):
        game = make_game()
        for _ in range(4):
            game.auto_move()
            if game.players[0].surrendered:
                break
            game.current_turn = 0

        self.assertTrue(game.players[0].surrendered)
        self.assertEqual(game.players[0].auto_turns, 4)
        self.assertFalse(game.finished)
        self.assertEqual(game.players[0].place, 4)

    def test_manual_wall_resets_automatic_move_streak(self):
        game = make_game()
        game.players[0].auto_turns = 3
        self.assertTrue(game.place_wall(0, 0, 0, "horizontal"))
        self.assertEqual(game.players[0].auto_turns, 0)

    def test_manual_move_resets_automatic_move_streak(self):
        game = make_game()
        game.players[0].auto_turns = 3
        self.assertTrue(game.move(0, 1, 5))
        self.assertEqual(game.players[0].auto_turns, 0)

    def test_surrendering_current_player_starts_the_next_players_clock(self):
        game = make_game()
        game.turn_deadline = 120
        self.assertTrue(game.surrender(0))
        self.assertEqual(game.current_turn, 1)
        self.assertEqual(game.turn_serial, 1)
        self.assertGreater(game.turn_deadline, 120)

    def test_eliminated_player_is_not_counted_as_an_obstacle(self):
        game = make_game()
        game.players[0].row, game.players[0].col = 4, 4
        game.players[1].row, game.players[1].col = 4, 5
        game.players[2].row, game.players[2].col = 4, 6
        game.players[3].row, game.players[3].col = 4, 7
        game.players[1].active = False
        self.assertIn((4, 5), game.legal_moves(0))


if __name__ == "__main__":
    unittest.main()
