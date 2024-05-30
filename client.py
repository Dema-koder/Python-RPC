import time
import argparse
from typing import Iterable
from enum import Enum, StrEnum
import grpc
import tic_tac_toe_pb2 as ttt
import tic_tac_toe_pb2_grpc as ttt_grpc


class Player(StrEnum):
    NOUGHT = "O"
    CROSS = "X"

    def mark(self) -> ttt.Mark:
        if self == Player.NOUGHT:
            return ttt.MARK_NOUGHT
        if self == Player.CROSS:
            return ttt.MARK_CROSS
        raise Exception("Invalid player.")

    def equals_mark(self, mark: ttt.Mark) -> bool:
        return self.mark() == mark


class Action(Enum):
    CREATE_GAME = 1
    CONNECT_TO_GAME = 2


def prompt_action() -> Action:
    while True:
        print("Please, choose an option:")
        print(" (1) create a new game")
        print(" (2) connect to a game")
        answer = input("> ")

        try:
            answer = int(answer.strip())
        except ValueError:
            continue

        for item in Action:
            if item.value == answer:
                return item


def prompt_player() -> Player:
    while True:
        answer = input("Choose a player (X/O): ").upper()
        if answer == Player.NOUGHT.value:
            return Player.NOUGHT
        if answer == Player.CROSS.value:
            return Player.CROSS


def prompt_game_id() -> int:
    while True:
        try:
            return int(input("Enter game ID to connect: "))
        except ValueError:
            continue


def prompt_move(player: Player, occupied: set[int]) -> int:
    while True:
        try:
            move = int(input(f"Your move ({player.value}): "))
        except ValueError:
            continue
        if not (1 <= move and move <= 9):
            print("Move must be in range [1,9].")
        elif move in occupied:
            print("This cell is already occupied.")
        else:
            return move


def draw_field(
    moves: Iterable[ttt.Move],
    draw_possible_moves: bool,
):
    cells = [i if draw_possible_moves else " " for i in range(1, 10)]
    for move in moves:
        if Player.CROSS.equals_mark(move.mark):
            cells[move.cell-1] = Player.CROSS.value
        elif Player.NOUGHT.equals_mark(move.mark):
            cells[move.cell-1] = Player.NOUGHT.value
    print(
        f"┌───┬───┬───┐\n"
        f"│ {cells[0]} │ {cells[1]} │ {cells[2]} │\n"
        f"├───┼───┼───┤\n"
        f"│ {cells[3]} │ {cells[4]} │ {cells[5]} │\n"
        f"├───┼───┼───┤\n"
        f"│ {cells[6]} │ {cells[7]} │ {cells[8]} │\n"
        f"└───┴───┴───┘"
    )


def play_game(
    stub: ttt_grpc.TicTacToeStub,
    game: ttt.Game,
    player: Player,
):
    while not game.is_finished:
        if player.equals_mark(game.turn):
            draw_field(game.moves, draw_possible_moves=True)
            occupied = set(move.cell for move in game.moves)
            cell = prompt_move(player, occupied)
            print()
            move = ttt.Move(mark=player.mark(), cell=cell)
            game = stub.MakeMove(ttt.MakeMoveRequest(game_id=game.id, move=move))
        else:
            draw_field(game.moves, draw_possible_moves=False)
            print("Waiting for the opponent's move...\n")
            while not game.is_finished and not player.equals_mark(game.turn):
                time.sleep(1)
                game = stub.GetGame(ttt.GetGameRequest(game_id=game.id))

    print("[ Game over ]")
    draw_field(game.moves, draw_possible_moves=False)

    if not game.HasField("winner"):
        print("Draw.")
    elif player.equals_mark(game.winner):
        print("🎉 You won! 🎉")
    else:
        print("You lose.")


def main(server_address: str):
    with grpc.insecure_channel(server_address) as channel:
        stub = ttt_grpc.TicTacToeStub(channel)

        print("Welcome to Tic-Tac-Toe! 👋\n")

        action = prompt_action()
        if action == Action.CREATE_GAME:
            player = prompt_player()
            print(f"Creating a new game...")
            game = stub.CreateGame(ttt.CreateGameRequest())
        elif action == Action.CONNECT_TO_GAME:
            game_id = prompt_game_id()
            player = prompt_player()
            print(f"Retrieving a game (ID={game_id})...")
            game = stub.GetGame(ttt.GetGameRequest(game_id=game_id))
            try:
                game = stub.GetGame(ttt.GetGameRequest(game_id=game_id))
            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.NOT_FOUND:
                    print(f"Error: game with ID={game_id} is not found.")
                    return
                else:
                    raise e
        else:
            raise Exception(f"Invalid action: {action}")

        print(f"Playing a game (ID={game.id}) as player {player}.\n")
        play_game(stub, game, player)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("server_address", help="Address of the Tic-Tac-Toe server.")
    args = parser.parse_args()

    try:
        main(args.server_address)
    except grpc.RpcError as e:
        print(f"gRPC error (code={e.code()}): {e.details()}")
    except KeyboardInterrupt:
        print("Exiting...")
