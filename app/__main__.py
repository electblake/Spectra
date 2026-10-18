import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from app.ui.main_ui import main

    main()
