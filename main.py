import os
from core.engine import GalGameEngine


def select_character():
    """控制台角色选择"""
    char_root = "assets/characters"

    if not os.path.exists(char_root):
        print(f"❌ 错误：找不到目录 {char_root}")
        return None

    chars = [d for d in os.listdir(char_root) if os.path.isdir(os.path.join(char_root, d))]
    if not chars:
        print("❌ 错误：assets/characters/ 下没有任何角色文件夹")
        return None

    print("\n" + "=" * 30)
    print("   Box-of-GalGame-Sister")
    print("=" * 30)
    print("请选择要加载的角色：\n")

    for i, name in enumerate(chars):
        print(f"  [{i + 1}] {name}")

    print("\n" + "-" * 30)
    choice = input(f"请输入序号 (1-{len(chars)}) [默认1]: ").strip()

    if not choice:
        return chars[0]

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(chars):
            return chars[idx]
        else:
            print("⚠️ 输入序号无效，自动选择第一个角色")
            return chars[0]
    except ValueError:
        print("⚠️ 输入格式错误，自动选择第一个角色")
        return chars[0]


if __name__ == "__main__":
    char_id = select_character()

    if char_id:
        print(f"\n🚀 正在启动引擎，加载角色 [{char_id}] ...")
        print("提示：按 Enter 发送截图，Alt+1~9 切换表情")
        try:
            engine = GalGameEngine(char_id)
            engine.start()
        except KeyboardInterrupt:
            print("\n👋 程序已退出")
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            input("按回车键退出...")
    else:
        input("按回车键退出...")
