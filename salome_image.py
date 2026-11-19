"""Salome-Meca SIF の検査と中断可能なストリーム取得。"""
import http.client
import os
import struct
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

FILENAME = "salome_meca-lgpl-2025.1.0-1-20251026-scibian-12.sif"
RELEASE_PAGE = "https://open-simulation-center.org/en/downloads/code_aster/SALOME_MECA/2025"


def image_size(header):
    if len(header) != 128 or header[32:45] != b"SIF_MAGIC\x0001\x00":
        raise ValueError("SIF を確認できません。配布ページから Linux 版 .sif の直接リンクを取得してください。")
    offset, length = struct.unpack_from("<qq", header, 112)
    if offset < 128 or length <= 0:
        raise ValueError("SIF ヘッダーのデータ範囲が不正です。")
    return offset + length


def verify_image(path):
    with path.open("rb") as stream:
        expected = image_size(stream.read(128))
    if path.stat().st_size != expected:
        raise ValueError("SIF のサイズが一致しません。ダウンロードの完了を確認してください。")


def transfer(url, partial, progress):
    # Compare the SIF UUID and full header even when the provider reissues a signed URL.
    response = urlopen(Request(url, headers={"Accept-Encoding": "identity"}), timeout=90)
    try:
        header = response.read(128)
        if len(header) < 128:
            raise EOFError("配布サーバーからの受信が中断されました。")
        expected = image_size(header)
        offset = 0
        if partial.exists():
            with partial.open("rb") as stream:
                if stream.read(128) == header:
                    offset = partial.stat().st_size
        if offset == expected:
            return
        if 128 <= offset < expected:
            headers = {"Range": f"bytes={offset}-", "Accept-Encoding": "identity"}
            validator = response.headers.get("ETag") or response.headers.get("Last-Modified")
            if validator and not validator.startswith("W/"):
                headers["If-Range"] = validator
            response.close()
            response = urlopen(Request(url, headers=headers), timeout=90)
            if response.status == 206:
                if response.headers.get("Content-Range") != f"bytes {offset}-{expected-1}/{expected}":
                    raise ValueError("配布サーバーの再開位置が一致しません。")
            elif response.status == 200:
                header = response.read(128)
                expected = image_size(header)
                offset = 0
            else:
                raise ValueError("配布サーバーが再開要求を処理できませんでした。")
        else:
            offset = 0
        with partial.open("ab" if offset else "wb") as output:
            if not offset:
                output.write(header)
                offset = len(header)
            last_report = 0
            while True:
                if time.monotonic() - last_report >= 1:
                    progress(f"Salome-Meca を取得中… {offset / 2**20:.0f} / {expected / 2**20:.0f} MiB")
                    last_report = time.monotonic()
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                offset += len(chunk)
            if offset != expected:
                raise EOFError("SIF の受信が途中で終了しました。")
    finally:
        response.close()


def prepare_image(source, progress):
    if not source.lower().startswith("https://"):
        path = Path(source)
        verify_image(path)
        return path.resolve()
    if not urlsplit(source).hostname:
        raise ValueError("公式配布ファイルの HTTPS URL を指定してください。")
    cache = Path(os.environ["LOCALAPPDATA"], "WSL-Manager", "Salome-Meca")
    cache.mkdir(parents=True, exist_ok=True)
    image = cache / FILENAME
    partial = image.with_suffix(".sif.part")
    import msvcrt
    with (cache / "download.lock").open("a+b") as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise RuntimeError("別のマネージャーが Salome-Meca を取得中です。") from error
        if image.exists():
            verify_image(image)
            return image
        for attempt in range(6):
            try:
                transfer(source, partial, progress)
                break
            except (URLError, http.client.HTTPException, TimeoutError, ConnectionError, EOFError) as error:
                if isinstance(error, HTTPError) and error.code not in (408, 429, 500, 502, 503, 504):
                    raise RuntimeError(f"配布元の応答は HTTP {error.code} です。新しい直接リンクで再実行してください。") from None
                if attempt == 5:
                    raise RuntimeError("通信が中断しました。取得済みデータを保持しました。同じソフトを選び再実行してください。") from None
                delay = min(2 ** (attempt + 1), 30)
                progress(f"通信が中断しました。{delay} 秒後に再接続します…")
                time.sleep(delay)
        verify_image(partial)
        partial.replace(image)
        return image
