# main.py
from gui.main_window import CoreController
import customtkinter as ctk

if __name__ == "__main__":
    app = ctk.CTk()
    core = CoreController(app)
    app.mainloop()