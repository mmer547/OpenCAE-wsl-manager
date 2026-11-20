"""パスワード設定で停止したマネージャー作成環境を PowerShell から再開する。"""
import argparse
import getpass

from wsl_manager import CAE_PROFILES, validate_account, wsl


def repair(name, user):
    root = ("-d", name, "-u", "root", "--exec")
    # Only recover the specific interruption before the installation plan was saved.
    wsl(*root, "test", "-f", "/root/resume.sh")
    wsl(*root, "test", "!", "-e", "/root/wsl-manager-plan")
    account = wsl(*root, "getent", "passwd", user).split(":")
    if len(account) != 7 or account[0] != user or int(account[2]) < 1000 or account[5] != "/home/" + user:
        raise ValueError("作成時に指定した一般ユーザー名を確認してください。")
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
    password = getpass.getpass("Linux パスワード: ")
    validate_account(user, password, getpass.getpass("確認用パスワード: "))
    try:
        wsl(*root, "/usr/sbin/chpasswd", "--crypt-method", "YESCRYPT",
            input_data=f"{user}:{password}\n".encode())
    except RuntimeError:
        raise RuntimeError("パスワードの設定に失敗しました。") from None
    wsl(*root, "usermod", "-s", "/bin/bash", user)
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
    parser.add_argument("user", help="環境作成時に指定した Linux ユーザー名")
    args = parser.parse_args()
    try:
        repair(args.name, args.user)
    except (RuntimeError, OSError, ValueError) as error:
        parser.exit(1, f"復旧を停止しました。{error}\n")
