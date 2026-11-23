"""マネージャー作成環境の初期設定を再開するか、既存環境の sudo を修復する。"""
import argparse
import getpass
from pathlib import Path

from wsl_manager import CAE_PROFILES, configure_sudo, validate_account, wsl


def check_account(root, user):
    account = wsl(*root, "getent", "passwd", user).split(":")
    if len(account) != 7 or account[0] != user or int(account[2]) < 1000 or account[5] != "/home/" + user:
        raise ValueError("作成時に指定した一般ユーザー名を確認してください。")
    return account


def repair_sudo(name, user):
    root = ("-d", name, "-u", "root", "--exec")
    if user is None:
        user = wsl(*root, "cat", "/root/wsl-manager-user")
    check_account(root, user)
    configure_sudo(root, user)
    print(f"「{name}」の {user} に sudo を設定しました。ターミナルを開き直し、sudo whoami で確認してください。")


def repair(name, user):
    root = ("-d", name, "-u", "root", "--exec")
    # Only recover the specific interruption before the installation plan was saved.
    wsl(*root, "test", "-f", "/root/resume.sh")
    wsl(*root, "test", "!", "-e", "/root/wsl-manager-plan")
    account = check_account(root, user)
    files = set(wsl(*root, "find", "/root", "-maxdepth", "1", "-type", "f",
                    "-name", "*_setup.sh", "-printf", "%f\\n").splitlines())
    steps = []
    for profile in CAE_PROFILES.values():
        if profile.setup_script in files:
            for script in (*profile.supporting_scripts, profile.setup_script):
                if script not in files:
                    raise ValueError(f"復旧に必要な {script} がありません。")
                if script not in steps:
                    steps.append(script)
    if not steps or files != set(steps):
        raise ValueError("転送済みスクリプトとこの版のセットアップ内容が一致しません。")
    print(f"対象: {name} / {user}\n再開する処理: {', '.join(steps)}")
    status = wsl(*root, "/usr/bin/passwd", "-S", user).split()
    if len(status) < 2 or status[0] != user or status[1] not in {"P", "L", "NP"}:
        raise ValueError("パスワードの設定状態を確認できませんでした。")
    if status[1] != "P":
        password = getpass.getpass("Linux パスワード: ")
        validate_account(user, password, getpass.getpass("確認用パスワード: "))
        try:
            wsl(*root, "/usr/sbin/chpasswd", "--crypt-method", "YESCRYPT",
                input_data=f"{user}:{password}\n".encode())
        except RuntimeError:
            raise RuntimeError("パスワードの設定に失敗しました。") from None
    if account[6].strip() != "/bin/bash":
        wsl(*root, "/usr/sbin/usermod", "-s", "/bin/bash", user)
    resume = Path(__file__).resolve().parent / "scripts" / "cae" / "resume.sh"
    wsl(*root, "tee", "/root/resume.sh", input_data=resume.read_text(encoding="utf-8").encode())
    configure_sudo(root, user)
    wsl("--manage", name, "--set-default-user", user)
    wsl(*root, "tee", "/root/wsl-manager-user", input_data=(user + "\n").encode())
    wsl(*root, "tee", "/root/wsl-manager-plan", input_data=("\n".join(steps) + "\n").encode())
    for script in steps:
        print(f"{script} を実行中…", flush=True)
        wsl(*root, "bash", "/root/resume.sh", script)
    wsl("--terminate", name)
    print(f"「{name}」のセットアップが完了しました。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="WSL 登録名")
    parser.add_argument("--sudo-only", action="store_true", help="既存環境の sudo のみ修復する")
    parser.add_argument("user", nargs="?", help="環境作成時に指定した Linux ユーザー名")
    args = parser.parse_args()
    try:
        if args.sudo_only:
            repair_sudo(args.name, args.user)
        elif args.user:
            repair(args.name, args.user)
        else:
            parser.error("初期設定を再開するには Linux ユーザー名を指定してください。")
    except (RuntimeError, OSError, ValueError) as error:
        parser.exit(1, f"復旧を停止しました。{error}\n")
