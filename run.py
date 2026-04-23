"""
율재부동산 영업 데이터 자산화 시스템 - 메인 진입점.

실행 방법:
  API 서버:   python run.py api
  대시보드:   python run.py dashboard
  파일 분석:  python run.py analyze <audio_file> <phone_number>
  배치 처리:  python run.py batch <directory>
  DB 초기화:  python run.py init-db
"""
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="율재부동산 영업 데이터 자산화 시스템", add_completion=False)
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@app.command("api")
def run_api(
    host: str = typer.Option("0.0.0.0", help="서버 호스트"),
    port: int = typer.Option(8000, help="서버 포트"),
    reload: bool = typer.Option(False, help="자동 리로드 (개발용)"),
):
    """FastAPI REST API 서버를 시작합니다."""
    import uvicorn
    from api import create_app
    from storage import init_db

    init_db()
    console.print(f"[bold green]API 서버 시작: http://{host}:{port}[/bold green]")
    console.print(f"[dim]API 문서: http://{host}:{port}/docs[/dim]")
    uvicorn.run(create_app(), host=host, port=port, reload=reload)


@app.command("dashboard")
def run_dashboard(
    port: int = typer.Option(8501, help="대시보드 포트"),
):
    """Streamlit 대시보드를 시작합니다."""
    import subprocess
    dashboard_path = Path(__file__).parent / "dashboard" / "app.py"
    console.print(f"[bold blue]대시보드 시작: http://localhost:{port}[/bold blue]")
    subprocess.run(
        ["streamlit", "run", str(dashboard_path), "--server.port", str(port)],
        check=True,
    )


@app.command("analyze")
def analyze_file(
    audio_file: str = typer.Argument(..., help="분석할 오디오 파일 경로"),
    phone_number: str = typer.Argument(..., help="고객 전화번호"),
    agent_name: str = typer.Option("", help="담당 직원 이름"),
):
    """단일 통화 녹음 파일을 분석합니다."""
    from storage import init_db, get_db
    from automation import ProcessingPipeline

    if not Path(audio_file).exists():
        console.print(f"[red]파일을 찾을 수 없습니다: {audio_file}[/red]")
        raise typer.Exit(1)

    init_db()
    pipeline = ProcessingPipeline()

    console.print(f"[bold]파일 분석 시작: {audio_file}[/bold]")
    with console.status("AI 분석 중..."):
        with get_db() as db:
            result = pipeline.process_file_path(
                db=db,
                file_path=audio_file,
                phone_number=phone_number,
                agent_name=agent_name,
            )

    table = Table(title="분석 결과", show_header=True, header_style="bold magenta")
    table.add_column("항목", style="cyan")
    table.add_column("값", style="white")
    table.add_row("통화 ID", str(result["call_id"]))
    table.add_row("기회 점수", f"{result['opportunity_score']}점")
    table.add_row("주요 의향", result["dominant_intent"])
    table.add_row("거래 성사 확률", f"{result['deal_probability']}%")
    table.add_row("자동 팔로업", f"{result['follow_ups_created']}건 생성")
    console.print(table)


@app.command("batch")
def batch_process(
    directory: str = typer.Argument(..., help="오디오 파일이 있는 디렉토리"),
    agent_name: str = typer.Option("", help="담당 직원 이름"),
):
    """디렉토리의 모든 오디오 파일을 일괄 처리합니다."""
    from storage import init_db, get_db
    from automation import ProcessingPipeline

    if not Path(directory).is_dir():
        console.print(f"[red]디렉토리를 찾을 수 없습니다: {directory}[/red]")
        raise typer.Exit(1)

    init_db()
    pipeline = ProcessingPipeline()

    console.print(f"[bold]배치 처리 시작: {directory}[/bold]")
    with get_db() as db:
        results = pipeline.batch_process_directory(db=db, directory=directory, agent_name=agent_name)

    table = Table(title=f"배치 처리 결과 ({len(results)}건)")
    table.add_column("파일", style="cyan")
    table.add_column("상태", style="white")
    table.add_column("기회점수", justify="right")
    table.add_column("의향", style="dim")

    for r in results:
        if r["success"]:
            table.add_row(
                r["file"], "[green]완료[/green]",
                str(r.get("opportunity_score", "–")),
                r.get("dominant_intent", "–"),
            )
        else:
            table.add_row(r["file"], f"[red]실패: {r.get('error', '')}[/red]", "–", "–")

    console.print(table)


@app.command("init-db")
def init_database():
    """데이터베이스를 초기화합니다."""
    from storage import init_db
    init_db()
    console.print("[green]데이터베이스 초기화 완료[/green]")


if __name__ == "__main__":
    app()
