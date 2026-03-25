import typer

app = typer.Typer()


@app.command()
def main(cnpj: str) -> None:
    """Avalia fundo de investimento brasileiro por CNPJ."""
    typer.echo(f"fundos-br: {cnpj} (not yet implemented)")


if __name__ == "__main__":
    app()
