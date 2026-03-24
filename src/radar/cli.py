import typer

app = typer.Typer()

@app.command()
def acao(ticker: str, json: bool = False, plain: bool = False):
    """Consulta cotação e preços teto de uma ação."""
    typer.echo(f"acao {ticker}")

@app.command()
def fii(ticker: str, json: bool = False, plain: bool = False):
    """Consulta cotação e preços teto de um FII."""
    typer.echo(f"fii {ticker}")

@app.command()
def indices():
    """Exibe índices de referência BR e US."""
    typer.echo("indices")
