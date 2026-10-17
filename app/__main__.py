import multiprocessing

from app.ui.main_ui import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
