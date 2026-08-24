import logging
import sys
import time
from typing import List, Any, Optional, Union, Dict, Callable
from contextlib import contextmanager

from rich.logging import RichHandler
from rich.console import Console
from rich.table import Table
from rich.progress import (
    Progress, 
    TextColumn, 
    BarColumn, 
    TaskProgressColumn, 
    TimeRemainingColumn,
    TimeElapsedColumn,
    SpinnerColumn
)

class Logger:
    """
    An enhanced logger using the Rich library for beautiful, colorized console 
    output, file logging, and integrated progress tracking.
    """
    def __init__(
        self, 
        name: str = "Application", 
        log_file: str = "application.log", 
        level: int = logging.DEBUG,
        console: Optional[Console] = None
    ):
        # Configure the logging system with a RichHandler for console output
        self.console = console or Console()
        
        # Create a custom formatter for file logs
        file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        
        # Create handlers
        rich_handler = RichHandler(
            rich_tracebacks=True,
            console=self.console,
            markup=True,
            show_level=False,
            show_path=True
        )
        
        file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        file_handler.setFormatter(file_formatter)
        
        # Configure root logger
        logging.basicConfig(
            level=level,
            format="%(message)s",
            datefmt="[%Y-%m-%d %H:%M:%S]",
            handlers=[rich_handler, file_handler]
        )
        
        self.logger = logging.getLogger(name)

    def info(self, message: str) -> None:
        """Log an info level message."""
        self.logger.info(f"[cyan][INFO][/cyan] {message}", stacklevel=2)

    def warning(self, message: str, exc_info: bool = False) -> None:
        """Log a warning level message with optional exception info."""
        self.logger.warning(f"[yellow][WARNING][/yellow] {message}", exc_info=exc_info, stacklevel=2)

    def error(self, message: str, exc_info: bool = False) -> None:
        """Log an error level message with optional exception info."""
        self.logger.error(f"[red][ERROR][/red] {message}", exc_info=exc_info, stacklevel=2)

    def debug(self, message: str) -> None:
        """Log a debug level message."""
        self.logger.debug(f"[dim][DEBUG][/dim] {message}", stacklevel=2)

    def success(self, message: str) -> None:
        """
        Log a success message.
        (Success messages are logged as INFO with a distinct [SUCCESS] tag.)
        """
        self.logger.info(f"[green][SUCCESS][/green] {message}", stacklevel=2)
        
    def critical(self, message: str, exc_info: bool = True) -> None:
        """Log a critical error message with exception info by default."""
        self.logger.critical(f"[white on red][CRITICAL][/white on red] {message}", exc_info=exc_info, stacklevel=2)

    def log_table(self, headers: List[str], rows: List[List[Any]], title: str = "Data Table") -> None:
        """
        Log tabular data as a rich formatted table.
        """
        table = Table(title=title, expand=True)
        
        for header in headers:
            table.add_column(
                header, 
                justify="center", 
                style="cyan", 
                overflow="fold", 
                no_wrap=False
            )
        
        for row in rows:
            table.add_row(*[str(item) for item in row])
        
        self.console.print(table)
        self.logger.info(f"Table: {title} - {len(rows)} rows", stacklevel=2)

    @contextmanager
    def progress_bar(
        self, 
        total: Optional[int] = None, 
        description: str = "Processing", 
        transient: bool = True
    ):
        """
        Create and yield a progress bar context manager.
        """
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            console=self.console,
            transient=transient
        )
        
        with progress:
            task_id = progress.add_task(description, total=total)
            
            try:
                class ProgressUpdater:
                    def __init__(self, progress_obj, task_id):
                        self.progress = progress_obj
                        self.task_id = task_id
                        self.start_time = time.time()
                        
                    def update(self, advance: int = 1, waiting: bool = False, retry_cnt: int = 0):
                        description = f"{progress.tasks[self.task_id].description}"
                        if waiting:
                            description = f"{description} (waiting, retry: {retry_cnt})"
                            self.progress.update(self.task_id, description=description)
                        self.progress.update(self.task_id, advance=advance)
                    
                    def set_description(self, description: str):
                        self.progress.update(self.task_id, description=description)
                    
                    def set_total(self, total: int):
                        self.progress.update(self.task_id, total=total)
                
                yield ProgressUpdater(progress, task_id)
                
            finally:
                progress.update(task_id, completed=True)
                
    def indeterminate_spinner(self, description: str = "Working"):
        """Create a spinner for operations with unknown duration."""
        return self.progress_bar(total=None, description=description)
