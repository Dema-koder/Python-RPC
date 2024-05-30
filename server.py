import argparse
from typing import Iterable, Optional
from concurrent import futures
import threading

import grpc

import tic_tac_toe_pb2_grpc as ttt_grpc
import tic_tac_toe_pb2 as ttt


def get_winner(moves: Iterable[ttt.Move]) -> Optional[ttt.Mark]:
    winning_combinations = (
        (1, 2, 3), (4, 5, 6), (7, 8, 9),  # Rows
        (1, 4, 7), (2, 5, 8), (3, 6, 9),  # Cols
        (1, 5, 9), (3, 5, 7),             # Diagonals
    )

    x_moves = []
    o_moves = []

    for move in moves:
        if move.mark == ttt.MARK_CROSS:
            x_moves.append(move.cell)
        elif move.mark == ttt.MARK_NOUGHT:
            o_moves.append(move.cell)

    for combination in winning_combinations:
        if all((cell in x_moves) for cell in combination):
            return ttt.MARK_CROSS
        if all((cell in o_moves) for cell in combination):
            return ttt.MARK_NOUGHT

    return None


class TicTacToeServicer(ttt_grpc.TicTacToeServicer):
    def __init__(self):
        self.games = []
        self.lock = threading.Lock()

    def find_game_by_id(self, game_id):
        index = -1
        for i in range(len(self.games)):
            if self.games[i].id == game_id:
                index = i
        return index

    def CreateGame(self, request, context):
        with self.lock:
            new_game = ttt.Game()
            print("CreateGame()")

            new_game.id = len(self.games) + 1
            new_game.is_finished = False
            new_game.turn = ttt.Mark.MARK_CROSS

            self.games.append(new_game)

            return new_game

    def GetGame(self, request, context):
        game_id = request.game_id
        print(f"GetGame(game_id={game_id})")

        with self.lock:
            index = self.find_game_by_id(game_id)
            if index == -1:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details('Game not found')
                return ttt.Game()

            return self.games[index]

    def MakeMove(self, request, context):
        game_id = request.game_id
        move = request.move
        print(f"MakeMove(game_id={game_id}, move=Move(mark={move.mark}, cell={move.cell}))")

        with self.lock:
            index = self.find_game_by_id(game_id)

            if move.cell > 9 or move.cell < 1:
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Move's cell is invalid")

            if index == -1:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details('Game not found')
                return ttt.Game()

            for prev_move in self.games[index].moves:
                if prev_move.cell == move.cell:
                    context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                    context.set_details("Move's cell occupied")
                    return ttt.Game()

            if self.games[index].is_finished:
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("Game is already finished")
                return ttt.Game()

            if self.games[index].turn != move.mark:
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("It is not the player's turn")
                return ttt.Game()

            self.games[index].moves.append(move)
            winner = get_winner(self.games[index].moves)
            if self.games[index].turn == ttt.MARK_CROSS:
                self.games[index].turn = ttt.MARK_NOUGHT
            else:
                self.games[index].turn = ttt.MARK_CROSS
            if winner is not None:
                self.games[index].is_finished = True
                self.games[index].winner = winner
            if len(self.games[index].moves) == 9:
                self.games[index].is_finished = True
            return self.games[index]


def main(port: str):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    ttt_grpc.add_TicTacToeServicer_to_server(TicTacToeServicer(), server)
    server.add_insecure_port(f"0.0.0.0:{port}")
    server.start()
    print(f"Server listening on 0.0.0.0:{port}...")
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        print("Shutting down")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("port")
    args = parser.parse_args()

    try:
        main(args.port)
    except KeyboardInterrupt:
        print("Exiting...")
