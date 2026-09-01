from extensible_ai_workspace import main


def test_main_prints_greeting(capsys) -> None:
    main()

    captured = capsys.readouterr()

    assert captured.out == "Hello from extensible-ai-workspace!\n"
