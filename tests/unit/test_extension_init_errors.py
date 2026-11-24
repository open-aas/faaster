"""A failing extension init() (run as a background task) must not be silently lost."""
import asyncio

from faaster.infra.aas_server import report_extension_task


async def test_failed_init_is_logged(capsys):
    async def init():
        raise RuntimeError("BadTypeMismatch writing Counter")

    task = asyncio.create_task(init())
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    reason = report_extension_task("Energy", task)

    assert reason == "init_error: RuntimeError"
    out = capsys.readouterr().out
    assert "extension_init_failed" in out and "Energy" in out


async def test_successful_or_cancelled_init_reports_nothing(capsys):
    async def ok():
        return None

    done = asyncio.create_task(ok())
    await done
    cancelled = asyncio.create_task(asyncio.sleep(10))
    cancelled.cancel()
    await asyncio.sleep(0)

    assert report_extension_task("A", done) is None
    assert report_extension_task("B", cancelled) is None
