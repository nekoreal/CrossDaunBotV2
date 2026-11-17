from collections import deque
from dataclasses import dataclass
import time


BOARD_SIZE = 11
CENTER = (5, 5)
TURN_SECONDS = 20
WALLS_PER_PLAYER = 5
MAX_JUMPED_PLAYERS = 3
STARTING_POSITIONS = ((0, 5), (5, 10), (10, 5), (5, 0))
DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))


@dataclass
class Pawn:
    tg_id: int
    username: str
    photo_url: str
    row: int
    col: int
    walls: int = WALLS_PER_PLAYER
    active: bool = True
    surrendered: bool = False
    auto_turns: int = 0
    place: int | None = None


@dataclass(frozen=True)
class Wall:
    row: int
    col: int
    orientation: str


class QuoridorGame:
    def __init__(self, players: list[dict], now: float | None = None):
        if len(players) != 4:
            raise ValueError("A Quoridor game requires exactly four players")
        self.players = [
            Pawn(
                tg_id=int(player["tg_id"]),
                username=player["username"],
                photo_url=player.get("photo_url", ""),
                row=STARTING_POSITIONS[index][0],
                col=STARTING_POSITIONS[index][1],
            )
            for index, player in enumerate(players)
        ]
        self.walls: list[Wall] = []
        self.current_turn = 0
        self.winner: int | None = None
        self.finished = False
        self.surrender_order: list[int] = []
        self.finish_order: list[int] = []
        self.turn_serial = 0
        self.turn_deadline = (time.time() if now is None else now) + TURN_SECONDS

    def _inside(self, row: int, col: int) -> bool:
        return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE

    def _blocked(self, row: int, col: int, next_row: int, next_col: int) -> bool:
        if row != next_row:
            wall_row = min(row, next_row)
            return any(
                wall.orientation == "horizontal"
                and wall.row == wall_row
                and wall.col <= col <= wall.col + 1
                for wall in self.walls
            )

        wall_col = min(col, next_col)
        return any(
            wall.orientation == "vertical"
            and wall.col == wall_col
            and wall.row <= row <= wall.row + 1
            for wall in self.walls
        )

    def _legal_moves_from(self, player_index: int, origin: tuple[int, int]) -> list[tuple[int, int]]:
        occupied = {
            (pawn.row, pawn.col)
            for index, pawn in enumerate(self.players)
            if index != player_index and pawn.active
        }
        moves: set[tuple[int, int]] = set()

        for row_step, col_step in DIRECTIONS:
            next_cell = (origin[0] + row_step, origin[1] + col_step)
            if not self._inside(*next_cell) or self._blocked(*origin, *next_cell):
                continue
            if next_cell not in occupied:
                moves.add(next_cell)
                continue

            jumped = 0
            cursor = next_cell
            stopped_by_wall = False
            while cursor in occupied and jumped < MAX_JUMPED_PLAYERS:
                jumped += 1
                beyond = (cursor[0] + row_step, cursor[1] + col_step)
                if not self._inside(*beyond):
                    break
                if self._blocked(*cursor, *beyond):
                    stopped_by_wall = True
                    break
                cursor = beyond

            if jumped and self._inside(*cursor) and cursor not in occupied:
                moves.add(cursor)
            elif jumped and (stopped_by_wall or not self._inside(*cursor)):
                pivot = cursor if cursor in occupied else (
                    cursor[0] - row_step,
                    cursor[1] - col_step,
                )
                for side_row, side_col in ((-col_step, row_step), (col_step, -row_step)):
                    side = (pivot[0] + side_row, pivot[1] + side_col)
                    if (
                        self._inside(*side)
                        and side not in occupied
                        and not self._blocked(*pivot, *side)
                    ):
                        moves.add(side)

        return sorted(moves)

    def legal_moves(self, player_index: int | None = None) -> list[tuple[int, int]]:
        index = self.current_turn if player_index is None else player_index
        if self.finished or not 0 <= index < len(self.players) or not self.players[index].active:
            return []
        pawn = self.players[index]
        return self._legal_moves_from(index, (pawn.row, pawn.col))

    def move(self, player_index: int, row: int, col: int) -> bool:
        if self.finished or player_index != self.current_turn:
            return False
        if (row, col) not in self.legal_moves(player_index):
            return False

        pawn = self.players[player_index]
        pawn.row, pawn.col = row, col
        pawn.auto_turns = 0
        if (row, col) == CENTER:
            pawn.active = False
            pawn.place = len(self.finish_order) + 1
            self.finish_order.append(player_index)
            self._finish_if_ready()
        if not self.finished:
            self.advance_turn()
        return True

    def place_wall(self, player_index: int, row: int, col: int, orientation: str) -> bool:
        if self.finished or player_index != self.current_turn:
            return False
        if orientation not in ("horizontal", "vertical"):
            return False
        if not (0 <= row < BOARD_SIZE - 1 and 0 <= col < BOARD_SIZE - 1):
            return False
        if self.players[player_index].walls <= 0:
            return False

        wall = Wall(row, col, orientation)
        for existing in self.walls:
            if existing.orientation != orientation:
                if existing.row == row and existing.col == col:
                    return False
            elif orientation == "horizontal":
                if existing.row == row and abs(existing.col - col) < 2:
                    return False
            elif existing.col == col and abs(existing.row - row) < 2:
                return False

        self.walls.append(wall)
        if not all(
            self._has_path_to_center(index)
            for index, player in enumerate(self.players)
            if player.active
        ):
            self.walls.pop()
            return False

        self.players[player_index].walls -= 1
        self.players[player_index].auto_turns = 0
        self.advance_turn()
        return True

    def surrender(self, player_index: int) -> bool:
        if self.finished or not 0 <= player_index < len(self.players):
            return False
        pawn = self.players[player_index]
        if not pawn.active:
            return False
        pawn.active = False
        pawn.surrendered = True
        self.surrender_order.append(player_index)
        if player_index == self.current_turn:
            if not self._finish_if_ready():
                self.advance_turn()
        else:
            self._finish_if_ready()
        return True

    def _finish_if_ready(self) -> bool:
        remaining = [
            index for index, pawn in enumerate(self.players)
            if pawn.active and pawn.place is None
        ]
        if len(remaining) <= 1 and remaining:
            player_index = remaining[0]
            self.players[player_index].active = False
            self.players[player_index].place = len(self.finish_order) + 1
            self.finish_order.append(player_index)

        used_places = {
            pawn.place for pawn in self.players
            if pawn.place is not None
        }
        open_places = sorted(set(range(1, len(self.players) + 1)) - used_places, reverse=True)
        for player_index, place in zip(self.surrender_order, open_places):
            if self.players[player_index].place is None:
                self.players[player_index].place = place

        self.finished = all(pawn.place is not None for pawn in self.players)
        if self.finished:
            self.winner = next(
                index for index, pawn in enumerate(self.players)
                if pawn.place == 1
            )
        return self.finished

    def _has_path_to_center(self, player_index: int) -> bool:
        start = (self.players[player_index].row, self.players[player_index].col)
        queue = deque([start])
        visited = {start}
        while queue:
            row, col = queue.popleft()
            if (row, col) == CENTER:
                return True
            for row_step, col_step in DIRECTIONS:
                neighbor = (row + row_step, col + col_step)
                if (
                    self._inside(*neighbor)
                    and neighbor not in visited
                    and not self._blocked(row, col, *neighbor)
                ):
                    visited.add(neighbor)
                    queue.append(neighbor)
        return False

    def _distance_to_center(self, start: tuple[int, int]) -> int:
        queue = deque([(start, 0)])
        visited = {start}
        while queue:
            (row, col), distance = queue.popleft()
            if (row, col) == CENTER:
                return distance
            for row_step, col_step in DIRECTIONS:
                neighbor = (row + row_step, col + col_step)
                if (
                    self._inside(*neighbor)
                    and neighbor not in visited
                    and not self._blocked(row, col, *neighbor)
                ):
                    visited.add(neighbor)
                    queue.append((neighbor, distance + 1))
        return BOARD_SIZE * BOARD_SIZE

    def shortest_move(self, player_index: int | None = None) -> tuple[int, int] | None:
        index = self.current_turn if player_index is None else player_index
        if self.finished or not 0 <= index < len(self.players):
            return None

        pawn = self.players[index]
        start = (pawn.row, pawn.col)
        queue = deque([(start, None)])
        visited = {start}
        while queue:
            position, first_move = queue.popleft()
            if position == CENTER:
                return first_move
            for destination in self._legal_moves_from(index, position):
                if destination in visited:
                    continue
                visited.add(destination)
                queue.append((destination, destination if first_move is None else first_move))

        moves = self._legal_moves_from(index, start)
        if not moves:
            return None
        return min(moves, key=self._distance_to_center)

    def auto_move(self) -> tuple[int, int] | None:
        if self.finished:
            return None
        player_index = self.current_turn
        pawn = self.players[player_index]
        if not pawn.active:
            return None
        auto_turns = pawn.auto_turns + 1
        destination = self.shortest_move()
        if destination is None:
            self.surrender(player_index)
            return None
        if not self.move(player_index, *destination):
            self.surrender(player_index)
            return None
        pawn = self.players[player_index]
        if pawn.active:
            pawn.auto_turns = auto_turns
            if pawn.auto_turns >= 4:
                self.surrender(player_index)
        return destination

    def advance_turn(self, now: float | None = None) -> None:
        for offset in range(1, len(self.players) + 1):
            next_turn = (self.current_turn + offset) % len(self.players)
            if self.players[next_turn].active:
                self.current_turn = next_turn
                break
        self.turn_serial += 1
        self.turn_deadline = (time.time() if now is None else now) + TURN_SECONDS
