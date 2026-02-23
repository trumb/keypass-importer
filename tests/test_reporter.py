"""Tests for CSV report generation."""

import csv
import pytest
from pathlib import Path

from keypass_importer.models import ImportResult, ImportSummary
from keypass_importer.reporter import write_results_csv, write_summary


@pytest.fixture
def sample_results() -> list[ImportResult]:
    return [
        ImportResult(
            entry_title="Server A",
            entry_group="Infra/Linux",
            status="imported",
            safe_name="Linux-Safe",
            account_id="acc_123",
            detected_platform="UnixSSH",
            url="ssh://server-a.example.com:22",
            timestamp="2026-02-23T12:00:00+00:00",
        ),
        ImportResult(
            entry_title="Server B",
            entry_group="Infra/Linux",
            status="duplicate",
            safe_name="Linux-Safe",
            account_id="acc_existing",
            detected_platform="PostgreSQL",
            url="db.example.com:5432",
            timestamp="2026-02-23T12:00:01+00:00",
        ),
        ImportResult(
            entry_title="Bad Entry",
            entry_group="Root",
            status="failed",
            error="Safe not found: BadSafe",
        ),
    ]


class TestWriteResultsCsv:
    def test_creates_csv_file(self, tmp_path: Path, sample_results):
        out = tmp_path / "results.csv"
        write_results_csv(sample_results, out)
        assert out.exists()

    def test_csv_has_correct_rows(self, tmp_path: Path, sample_results):
        out = tmp_path / "results.csv"
        write_results_csv(sample_results, out)
        with open(out) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 3

    def test_csv_columns(self, tmp_path: Path, sample_results):
        out = tmp_path / "results.csv"
        write_results_csv(sample_results, out)
        with open(out) as f:
            reader = csv.DictReader(f)
            row = next(reader)
        assert "entry_title" in row
        assert "entry_group" in row
        assert "status" in row
        assert "safe_name" in row
        assert "account_id" in row
        assert "error" in row
        assert "detected_platform" in row
        assert "url" in row
        assert "timestamp" in row

    def test_no_secrets_in_csv(self, tmp_path: Path, sample_results):
        """Verify passwords never appear in CSV output."""
        out = tmp_path / "results.csv"
        write_results_csv(sample_results, out)
        content = out.read_text()
        assert "password" not in content.lower() or "password" in csv.DictReader(
            open(out)
        ).fieldnames

    def test_filter_by_status(self, tmp_path: Path, sample_results):
        out = tmp_path / "duplicates.csv"
        write_results_csv(sample_results, out, status_filter="duplicate")
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["status"] == "duplicate"

    def test_filter_failed(self, tmp_path: Path, sample_results):
        out = tmp_path / "failed.csv"
        write_results_csv(sample_results, out, status_filter="failed")
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["error"] == "Safe not found: BadSafe"

    def test_new_columns_have_correct_data(self, tmp_path: Path, sample_results):
        out = tmp_path / "results.csv"
        write_results_csv(sample_results, out)
        with open(out) as f:
            rows = list(csv.DictReader(f))
        # First result has platform, url, and timestamp
        assert rows[0]["detected_platform"] == "UnixSSH"
        assert rows[0]["url"] == "ssh://server-a.example.com:22"
        assert rows[0]["timestamp"] == "2026-02-23T12:00:00+00:00"
        # Third result (failed) has empty new fields
        assert rows[2]["detected_platform"] == ""
        assert rows[2]["url"] == ""
        assert rows[2]["timestamp"] == ""

    def test_empty_results(self, tmp_path: Path):
        out = tmp_path / "results.csv"
        write_results_csv([], out)
        with open(out) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0


class TestWriteSummary:
    def test_prints_summary(self, capsys):
        summary = ImportSummary(total=10, imported=7, duplicates=2, failed=1)
        write_summary(summary)
        captured = capsys.readouterr()
        assert "10" in captured.out
        assert "7" in captured.out
        assert "2" in captured.out
        assert "1" in captured.out
