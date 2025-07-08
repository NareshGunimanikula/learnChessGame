import tkinter as tk
from tkinter import messagebox

import chess
import chess.engine
import chess.polyglot
from PIL import Image, ImageTk

TILE_SIZE = 64
PIECE_PATH = "./pieces/"  # Folder containing wp.png, bp.png, etc.


class ChessGUI:
    def __init__(self, master, engine_path):
        self.game_over = False  # Track game state
        self.master = master
        self.engine_path = engine_path
        self.board = chess.Board()
        self.selected_square = None

        self.canvas = tk.Canvas(master, width=8 * TILE_SIZE, height=8 * TILE_SIZE)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)

        self.status_label = tk.Label(master, text="Your move", font=("Arial", 14))
        self.status_label.pack()

        self.move_history = tk.Text(master, height=10, width=50, font=("Courier", 10))
        self.move_history.pack()

        self.undo_button = tk.Button(master, text="⏪ Undo Last Turn", command=self.undo_last_turn)
        self.undo_button.pack(pady=5)

        self.new_game_button = tk.Button(master, text="🔁 New Game", command=self.reset_game)
        self.new_game_button.pack(pady=5)

        self.explanation_label = tk.Label(master, text="", font=("Arial", 11), fg="gray")
        self.explanation_label.pack(pady=3)

        # ✅ Load piece images AFTER Tk root is initialized
        self.piece_images = {}
        for color in ['w', 'b']:
            for piece in ['p', 'n', 'b', 'r', 'q', 'k']:
                img = Image.open(f"{PIECE_PATH}{color}{piece}.png").resize((TILE_SIZE, TILE_SIZE))
                self.piece_images[f"{color}{piece}"] = ImageTk.PhotoImage(img)

        self.draw_board()

    def undo_last_turn(self):
        # Undo both player and stockfish move, if available
        if len(self.board.move_stack) >= 2:
            self.board.pop()  # Undo stockfish
            self.board.pop()  # Undo player
            self.update_ui()
            self.status_label.config(text="⏪ Undid last turn.")
        elif len(self.board.move_stack) == 1:
            self.board.pop()
            self.update_ui()
            self.status_label.config(text="⏪ Undid your move.")
        else:
            self.status_label.config(text="Nothing to undo.")

    def draw_board(self):
        self.canvas.delete("all")
        color1 = "#EEEED2"
        color2 = "#769656"

        for rank in range(8):
            for file in range(8):
                color = color1 if (rank + file) % 2 == 0 else color2
                x1 = file * TILE_SIZE
                y1 = rank * TILE_SIZE
                x2 = x1 + TILE_SIZE
                y2 = y1 + TILE_SIZE
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

                piece = self.board.piece_at(chess.square(file, 7 - rank))
                if piece:
                    color = 'w' if piece.color == chess.WHITE else 'b'
                    symbol = piece.symbol().lower()
                    image = self.piece_images[f"{color}{symbol}"]
                    self.canvas.create_image(x1, y1, image=image, anchor="nw")

    def shade_board(self):
        self.canvas.create_rectangle(
            0, 0, 8 * TILE_SIZE, 8 * TILE_SIZE,
            fill="#444444", stipple="gray50", outline=""
        )

    def reset_game(self):
        self.board.reset()
        self.selected_square = None
        self.game_over = False
        self.status_label.config(text="New game started. Your move.")
        self.move_history.delete("1.0", tk.END)
        self.update_ui()

    def explain_move(self, board, move, prev_score=None):
        piece = board.piece_at(move.from_square)
        piece_name = piece.symbol().upper() if piece else "?"
        explanation = []
        color = "gray"

        # Quick tags
        if board.is_capture(move):
            explanation.append("Captures opponent's piece")
        if piece_name == 'P' and chess.square_file(move.to_square) in [2, 3, 4, 5]:
            explanation.append("Controls center")
        if piece_name == 'N':
            explanation.append("Develops knight")
        if piece_name == 'B':
            explanation.append("Activates bishop")
        if piece_name == 'K' and abs(chess.square_file(move.to_square) - chess.square_file(move.from_square)) > 1:
            explanation.append("Castles for safety")

        # Score-based grading
        if prev_score is not None:
            with chess.engine.SimpleEngine.popen_uci(self.engine_path) as engine:
                temp_board = board.copy()
                temp_board.push(move)
                result = engine.analyse(temp_board, chess.engine.Limit(time=0.5))
                score_after = result["score"].white().score(mate_score=10000)
                if score_after is not None:
                    diff = score_after - prev_score
                    if diff < -150:
                        explanation.append("Blunder")
                        color = "#B22222"
                    elif diff < -50:
                        explanation.append("Inaccuracy")
                        color = "#DAA520"
                    elif diff > 50:
                        explanation.append("Strong move")
                        color = "#228B22"
                    else:
                        explanation.append("Reasonable move")
                        color = "gray"
        return "; ".join(explanation), color

    def on_click(self, event):

        if self.game_over:
            self.status_label.config(text="Game is over. Press undo or reset to continue.")
            return

        file = event.x // TILE_SIZE
        rank = 7 - (event.y // TILE_SIZE)
        square = chess.square(file, rank)

        if self.selected_square is None:
            piece = self.board.piece_at(square)
            if piece and piece.color == self.board.turn:
                self.selected_square = square
        else:
            move = chess.Move(self.selected_square, square)
            if move in self.board.legal_moves:
                san = self.board.san(move)  # ✅ Get SAN before pushing
                board_copy = self.board.copy()
                explanation, color = self.explain_move(board_copy, move)
                self.board.push(move)
                self.update_ui()
                self.status_label.config(text=f"You played: {san}")
                self.explanation_label.config(text=f"🧠 {explanation}", fg=color)
                self.check_game_end()

                if not self.board.is_game_over():
                    self.master.after(500, self.stockfish_move)
            else:
                self.status_label.config(text="Illegal move. Try again.")
            self.selected_square = None

    def stockfish_move(self):
        with chess.engine.SimpleEngine.popen_uci(self.engine_path) as engine:
            result = engine.analyse(self.board, chess.engine.Limit(time=1))
            score = result["score"].white().score(mate_score=10000)
            best_move = engine.play(self.board, chess.engine.Limit(time=1)).move
            san = self.board.san(best_move)  # ✅ Get SAN before pushing
            board_copy = self.board.copy()
            explanation, color = self.explain_move(board_copy, best_move)
            self.board.push(best_move)
            self.explanation_label.config(text=f"🤖 {explanation}", fg=color)

            eval_str = "MATE" if score is None else f"{score / 100:+.2f}"
            self.status_label.config(text=f"Stockfish played: {san} | Eval: {eval_str}")
            self.explanation_label.config(text=f"🤖 {explanation}", fg=color)
            self.update_ui()
            self.check_game_end()

    def update_ui(self):
        self.draw_board()
        self.show_move_history()
        self.show_opening_name()

    def show_move_history(self):
        self.move_history.delete("1.0", tk.END)
        board_copy = chess.Board()
        moves = list(self.board.move_stack)
        lines = []

        for i in range(0, len(moves), 2):
            white_move = moves[i]
            white_san = board_copy.san(white_move)
            board_copy.push(white_move)

            if i + 1 < len(moves):
                black_move = moves[i + 1]
                black_san = board_copy.san(black_move)
                board_copy.push(black_move)
            else:
                black_san = ""

            lines.append(f"{i // 2 + 1}. {white_san} {black_san}")

        self.move_history.insert(tk.END, "\n".join(lines))

    def check_game_end(self):
        if self.board.is_checkmate():
            winner = "Black" if self.board.turn else "White"
            self.status_label.config(text=f"♔ Checkmate! {winner} wins.")
            self.game_over = True
            self.shade_board()
        elif self.board.is_stalemate():
            self.status_label.config(text="🤝 Stalemate! It's a draw.")
            self.game_over = True
            self.shade_board()
        elif self.board.is_insufficient_material():
            self.status_label.config(text="Draw: Insufficient material.")
            self.game_over = True
            self.shade_board()
        elif self.board.can_claim_draw():
            self.status_label.config(text="Draw by 50-move rule or repetition.")
            self.game_over = True
            self.shade_board()

    def show_opening_name(self):
        try:
            import chess.openings
            name = chess.openings.opening_name(self.board)
            self.master.title(f"♘ Chess Assistant - {name}")
        except:
            self.master.title("Chess Assistant")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("♟️ Chess Assistant (Player vs Stockfish)")

    # ✅ Update this to your actual Stockfish path
    stockfish_path = "C:/Users/gunim/Downloads/stockfish/stockfish-windows-x86-64-avx2.exe"
    app = ChessGUI(root, stockfish_path)
    root.mainloop()
