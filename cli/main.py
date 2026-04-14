import typer

app = typer.Typer(add_completion=False, invoke_without_command=True)

@app.callback()
def main(env: str = typer.Option("dev", "--env")) -> None:
    print(f"env={env}")
