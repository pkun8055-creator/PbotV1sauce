import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import re
import random
from difflib import SequenceMatcher
import datetime
import asyncio
from discord.ext import tasks
import sqlite3
from discord.ext import commands, tasks



# zoneinfo needs a time-zone database (tzdata) on some platforms (notably Windows).
# If tzdata is not installed, fall back to a fixed-offset timezone.
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

JST = None
if ZoneInfo is not None:
    try:
        JST = ZoneInfo("Asia/Tokyo")
    except Exception:
        JST = None

if JST is None:
    JST = datetime.timezone(datetime.timedelta(hours=9))

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()



# =====================
# テーブル作成
# =====================

cursor.execute("""
CREATE TABLE IF NOT EXISTS raid_texts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT UNIQUE
)
""")
conn.commit()

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_data (
    user_id INTEGER,
    guild_id INTEGER,
    coins INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0,
    last_message REAL DEFAULT 0,
    PRIMARY KEY (user_id, guild_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS count_game (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER,
    current_number INTEGER,
    x_number INTEGER,
    record INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_data (
    user_id INTEGER PRIMARY KEY,
    coins INTEGER DEFAULT 0
)
""")

# リマインダー（workクールタイム用）
cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    target_time TEXT,
    notification_type TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_data (
    user_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    coins INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, guild_id)
)
""")
conn.commit()

def load_json(filename):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump({}, f)
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

count_settings = load_json("count_settings.json")




# =====================
# 基本設定
# =====================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

OWNER_ID = [1297821384076165180, 1413790671407681676]

JST = datetime.timezone(datetime.timedelta(hours=9))  # JST固定



# =====================
# 正規表現（挨拶）
# =====================

PATTERNS = {
    re.compile("おはよう"): "おはよう",
    re.compile("こんにちは"): "こんにちは",
    re.compile("こんばんは"): "こんばんは",
    re.compile("はろー"): "はろー",
    re.compile("hello", re.I): "Hello",
    re.compile("hi", re.I): "Hi",
    re.compile("こーーんにーーちはーーーーー"): "こーーんにーーちはーーーーー",
    re.compile("こんにちわ"): "こんにちわ",
    re.compile("こーーんにーーちわーーーーー"): "こーーんにーーちわーーーーー",
    re.compile("こーんにーちはー"): "こーんにーちはー",
    re.compile("こーんにーちわー"): "こーんにーちわー",
    re.compile("あけおめ"): "あけおめ",
    re.compile("あけましておめでとうございます"): "あけましておめでとうございます",
    re.compile("よいお年を"): "よいお年を",
    re.compile("ベリークルシミマス"): "ベリークルシミマス",
    re.compile("ためかけこともろ"): "ためかけこともろ",
    re.compile("こんちゃ"): "こんちゃ",
    re.compile("おやすみ"): "おやすみ",
}


TOPICS = [
    "最近ハマっていることは？",
    "今一番欲しいものは何？",
    "好きなゲームは？",
    "マイクラで一番好きなアイテムは？",
    "朝型？夜型？",
    "今までで一番楽しかった出来事は？",
    "行ってみたい国は？",
    "好きな食べ物は？",
    "子供の頃の夢は？",
    "無人島に1つ持っていくなら？",
    "一番時間を溶かしたゲームは？",
    "昔ハマってたゲームは？",
    "1日だけ透明になれたら何する？",
    "マイクラで一番好きなブロックは？",
    "100万円もらったらまず何買う？",
    "タイムマシンあったら過去と未来どっち行く？",
    "無人島に連れていくならこのサーバーの誰？",

]
REPORT_CHANNEL_NAME = "ぴーbot通報ログ"
MAX_TIMEOUT_DAYS = 28
GREETING_ENABLED = True

STATUS_MESSAGES = [
    lambda: f"{len(bot.guilds)} サーバーに参加中",
    lambda: f"{sum(g.member_count for g in bot.guilds)} users",
    lambda: "荒らし・詐欺行為を検知します!",
    lambda: "/helpでコマンドを確認!"
]

GREETING_FILE = "greeting_settings.json"

def load_greeting_settings():
    if not os.path.exists(GREETING_FILE):
        return {}
    with open(GREETING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_greeting_settings(data):
    with open(GREETING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

greeting_settings = load_greeting_settings()

def get_coins(user_id, guild_id):
    cursor.execute(
        "SELECT coins FROM user_data WHERE user_id=? AND guild_id=?",
        (user_id, guild_id)
    )
    row = cursor.fetchone()
    return row[0] if row else 0


def add_coins(user_id, guild_id, amount):
    cursor.execute("""
        INSERT INTO user_data (user_id, guild_id, coins)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, guild_id)
        DO UPDATE SET coins = coins + ?
    """, (user_id, guild_id, amount, amount))
    conn.commit()


def reset_coins(user_id, guild_id):
    cursor.execute("""
        INSERT INTO user_data (user_id, guild_id, coins)
        VALUES (?, ?, 0)
        ON CONFLICT(user_id, guild_id)
        DO UPDATE SET coins = 0
    """, (user_id, guild_id))
    conn.commit()



async def send_count_embed(channel, settings):

    embed = discord.Embed(
        title="🎲 数字カウントゲーム開始！",
        description=(
            f"現在の数字：**{settings['current_number']}**\n"
            f"最高記録：**{settings['record']}**\n\n"
            f"⚠ 禁止数字：『{settings['x_number']}』を含んだら即終了！"
        ),
        color=discord.Color.green()
    )

    await channel.send(embed=embed)

# =====================
# コイン操作
# =====================
# =====================
# コイン管理（サーバー別）
# =====================

# user_data テーブルは既に作ってるけど念のため
# =====================
# テーブル作成（サーバー別コイン管理）
# =====================
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_data (
    user_id INTEGER,
    guild_id INTEGER,
    coins INTEGER DEFAULT 0,
    PRIMARY KEY(user_id, guild_id)
)
""")
conn.commit()


# コイン取得
def get_coins(user_id, guild_id):
    cursor.execute("SELECT coins FROM user_data WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
    result = cursor.fetchone()
    return result[0] if result else 0

# コイン追加
def add_coins(user_id, guild_id, amount):
    cursor.execute("""
    INSERT INTO user_data (user_id, guild_id, coins)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id, guild_id)
    DO UPDATE SET coins = coins + ?
    """, (user_id, guild_id, amount, amount))
    conn.commit()

# コイン設定
def set_coins(user_id, guild_id, amount):
    cursor.execute("""
    INSERT INTO user_data (user_id, guild_id, coins)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id, guild_id)
    DO UPDATE SET coins = ?
    """, (user_id, guild_id, amount, amount))
    conn.commit()

# コインリセット
def reset_coins(user_id, guild_id):
    cursor.execute("""
    UPDATE user_data SET coins = 0
    WHERE user_id = ? AND guild_id = ?
    """, (user_id, guild_id))
    conn.commit()




# =====================
# レベル設定テーブル
# =====================

cursor.execute("""
CREATE TABLE IF NOT EXISTS level_roles (
    guild_id INTEGER,
    level INTEGER,
    role_id INTEGER,
    PRIMARY KEY (guild_id, level)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS level_settings (
    guild_id INTEGER PRIMARY KEY,
    announce_channel INTEGER,
    log_channel INTEGER,
    announce_enabled INTEGER DEFAULT 1
)
""")



conn.commit()
try:
    cursor.execute("ALTER TABLE level_settings ADD COLUMN announce_enabled INTEGER DEFAULT 1")
    conn.commit()
except:
    pass


conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    channel_id INTEGER,
    target_time TEXT,
    cooldown_min INTEGER,
    notification_type TEXT
)
""")
conn.commit()


def get_coins(user_id: int) -> int:
    cursor.execute("SELECT coins FROM user_data WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

def add_coins(user_id: int, amount: int):
    cursor.execute("""
        INSERT INTO user_data (user_id, coins) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET coins = coins + ?
    """, (user_id, amount, amount))
    conn.commit()

def reset_coins(user_id: int):
    cursor.execute("""
        INSERT INTO user_data (user_id, coins) VALUES (?, 0)
        ON CONFLICT(user_id) DO UPDATE SET coins = 0
    """, (user_id,))
    conn.commit()



# =====================
# レベル計算
# =====================

def get_level(xp):
    return int((xp // 100) ** 0.5)


async def add_xp(member, guild, amount):

    user_id = member.id
    guild_id = guild.id
    now = datetime.datetime.utcnow().timestamp()

    cursor.execute("""
        SELECT xp, level, last_message
        FROM user_data
        WHERE user_id=? AND guild_id=?
    """, (user_id, guild_id))

    row = cursor.fetchone()

    if row:
        xp, level, last = row
    else:
        xp, level, last = 0, 0, 0

    # クールタイム（10秒）
    if now - last < 10:
        return

    xp += amount
    new_level = get_level(xp)

    cursor.execute("""
        INSERT INTO user_data (user_id, guild_id, xp, level, last_message)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, guild_id)
        DO UPDATE SET
            xp=?,
            level=?,
            last_message=?
    """, (user_id, guild_id, xp, new_level, now,
          xp, new_level, now))

    conn.commit()

    # レベルアップ
    if new_level > level:
        await level_up(member, guild, new_level, level)
        add_coins(member.id, guild.id, 100)


# =====================
# レベルアップ処理
# =====================

async def level_up(member, guild, new_level, old_level):

    # ロール付与
    cursor.execute("""
        SELECT role_id FROM level_roles
        WHERE guild_id=? AND level=?
    """, (guild.id, new_level))

    row = cursor.fetchone()

    if row:
        role = guild.get_role(row[0])
        if role:
            try:
                await member.add_roles(role)
            except:
                pass

    # 設定取得
    cursor.execute("""
        SELECT announce_channel, log_channel, announce_enabled
        FROM level_settings
        WHERE guild_id=?
    """, (guild.id,))

    setting = cursor.fetchone()

    announce_ch = None
    log_ch = None
    announce_enabled = True

    if setting:
        if setting[0]:
            announce_ch = guild.get_channel(setting[0])
        if setting[1]:
            log_ch = guild.get_channel(setting[1])
        announce_enabled = bool(setting[2])

    # 通知
    if announce_enabled and announce_ch:
        await announce_ch.send(
            f"🎉 {member.mention} さんが **Lv {new_level}** になりました！"
        )

    # ログ
    if log_ch:
        embed = discord.Embed(
            title="📜 レベルアップ",
            description=f"{member.mention}\nLv {old_level} → {new_level}",
            color=discord.Color.green()
        )
        await log_ch.send(embed=embed)





# =====================
# /level コマンド
# =====================

@tree.command(name="level", description="自分のレベル表示")
async def level(interaction: discord.Interaction):

    uid = interaction.user.id
    gid = interaction.guild.id

    cursor.execute("""
        SELECT xp, level
        FROM user_data
        WHERE user_id=? AND guild_id=?
    """, (uid, gid))

    row = cursor.fetchone()

    xp = row[0] if row else 0
    lvl = row[1] if row else 0

    embed = discord.Embed(
        title="📊 レベル情報",
        description=f"Lv: {lvl}\nXP: {xp}",
        color=discord.Color.blue()
    )

    await interaction.response.send_message(embed=embed)


# =====================
# /level_setting
# =====================

OWNER_ID = [
    1297821384076165180,  
    1413790671407681676   
]

# ...existing code...


# =====================
# レベル設定パネル
# =====================

class LevelPanel(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📢 通知ON/OFF", style=discord.ButtonStyle.green)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):

        gid = interaction.guild.id

        cursor.execute("""
            SELECT announce_enabled
            FROM level_settings
            WHERE guild_id=?
        """, (gid,))

        row = cursor.fetchone()

        enabled = 1
        if row:
            enabled = 0 if row[0] else 1

        cursor.execute("""
            INSERT INTO level_settings (guild_id, announce_enabled)
            VALUES (?, ?)
            ON CONFLICT(guild_id)
            DO UPDATE SET announce_enabled=?
        """, (gid, enabled, enabled))

        conn.commit()

        await interaction.response.send_message(
            f"通知を {'ON' if enabled else 'OFF'} にしました",
            ephemeral=True
        )


# =====================
# /level_settings パネル表示
# =====================

@tree.command(name="level_settings", description="レベル設定パネル")
async def level_settings(interaction: discord.Interaction):

    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message(
            "❌ 管理者のみ",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="⚙ レベル設定",
        description="ボタンで設定できます",
        color=discord.Color.orange()
    )

    await interaction.response.send_message(
        embed=embed,
        view=LevelPanel()
    )


# =====================
# ozeu（荒らし）検知
# =====================

OZEU_PATTERN = re.compile(r"おぜ+うLOL+")

def load_raid_texts():
    cursor.execute("SELECT text FROM raid_texts")
    rows = cursor.fetchall()
    return [row[0] for row in rows]

def is_ozeu(content: str) -> bool:
    # 正規表現検知（おぜう系）
    if OZEU_PATTERN.search(content):
        return True

    # 学習データ検知
    for text in load_raid_texts():
        if text in content:
            return True

    return False

# =====================
# 起動時処理
# =====================

async def update_presence():
    text = STATUS_MESSAGES[0]()
    await bot.change_presence(activity=discord.Game(name=text))

@bot.event
async def on_ready():
    print(f"BOT起動完了: {bot.user}")

    try:
        await bot.tree.sync()  # ← clear_commands削除！
        print("スラッシュコマンド同期完了")
    except Exception as e:
        print("同期失敗:", e)

    await update_presence()


    await update_presence()

    notify_channel_name = "bot・ぴーbot稼働通知"
    for ch in bot.get_all_channels():
        if ch.name == notify_channel_name:
            try:
                await ch.send("<@&1431935607562571938> ぴーbotが起動しました")
            except:
                pass

    if not reminder_loop.is_running():
        reminder_loop.start()

    if not pin_loop.is_running():
        pin_loop.start()
    
    if not status_loop.is_running():
        status_loop.start()
    
    






# =====================
# PIN常駐
# =====================

PIN_FILE = "pins.json"

def load_pins():
    if not os.path.exists(PIN_FILE):
        return {}
    with open(PIN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_pins(data):
    with open(PIN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

pins = load_pins()

@tasks.loop(seconds=5)
async def pin_loop():
    global pins
    changed = False

    for cid, data in list(pins.items()):
        channel = bot.get_channel(int(cid))
        if not channel:
            continue

        msg_id = data.get("message_id")
        content_now = (data.get("content") or "").strip()

        # =========================
        # 既存PINがある場合
        # =========================
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)

                # embedが存在し、descriptionが取れる場合のみ比較
                if msg.embeds and msg.embeds[0].description:
                    old_desc = msg.embeds[0].description.strip()

                    # ✅ 内容同じなら何もしない（ここが超重要）
                    if old_desc == content_now:
                        continue

                # 内容違う場合のみ削除
                await msg.delete()

            except discord.NotFound:
                # メッセージ消えてた場合は新規作成へ進む
                pass
            except Exception as e:
                print(f"PIN取得エラー: {e}")
                continue

        # =========================
        # 新規送信
        # =========================
        try:
            embed = discord.Embed(
                title="📌 PIN",
                description=content_now,
                color=discord.Color.green()
            )
            embed.set_footer(text=f'by {data.get("author", "unknown")}')

            new_msg = await channel.send(embed=embed)

            # ← ここが超重要（更新ループ止める核心）
            pins[cid]["message_id"] = new_msg.id
            changed = True

            print(f"PIN更新: {cid}")

        except Exception as e:
            print(f"PIN送信エラー: {e}")
            continue

    if changed:
        save_pins(pins)


# =====================
# on_message
# =====================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    content = message.content or ""

    is_staff = (
        message.author.guild_permissions.administrator or
        message.author.guild_permissions.manage_guild or
        message.author.guild_permissions.manage_messages
    )

    # =========================
    # 🚨 詐欺検知（最優先）
    # =========================

    file_count = len(message.attachments) + len(message.embeds)

    # 管理者でも検知はするが処罰はしないモード
    if "@everyone" in content and file_count == 4:
        user = message.author
        channel = message.channel
        guild = message.guild
        attachments = "\n".join(a.url for a in message.attachments)

        # 👇 管理者ならログだけ
        if is_staff:
            report_channel = discord.utils.get(guild.text_channels, name="ぴーbot通報ログ")
            if report_channel:
                embed = discord.Embed(
                    title="⚠ 管理者の詐欺パターン検知（処罰なし）",
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="ユーザー", value=f"{user} ({user.id})", inline=False)
                embed.add_field(name="チャンネル", value=channel.mention, inline=False)
                embed.add_field(name="内容", value=content or "（テキストなし）", inline=False)
                embed.add_field(name="添付ファイル", value=attachments, inline=False)
                await report_channel.send(embed=embed)

            # ★ ここでreturnしない！！！！
        else:
            await message.delete()

            warn = await channel.send(f"🚨 {user.mention} 詐欺スパムを検知しました")
            await warn.delete(delay=2)

            try:
                until = discord.utils.utcnow() + datetime.timedelta(days=28)
                await user.timeout(until, reason="画像4枚@everyone詐欺検知")
            except Exception as e:
                print("Timeout失敗:", e)

            report_channel = discord.utils.get(guild.text_channels, name="ぴーbot通報ログ")
            if report_channel:
                embed = discord.Embed(
                    title="🚨 詐欺スパム自動検知",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="ユーザー", value=f"{user} ({user.id})", inline=False)
                embed.add_field(name="チャンネル", value=channel.mention, inline=False)
                embed.add_field(name="内容", value=content or "（テキストなし）", inline=False)
                embed.add_field(name="添付ファイル", value=attachments, inline=False)
                await report_channel.send(embed=embed)

            return  # ← 一般ユーザーのみここで止める



    # =========================
    # ⚠ おぜう検知（管理者は除外）
    # =========================
    if is_ozeu(content) and not is_staff:
        await message.delete() 
        await message.channel.send(
            f"⚠ {message.author.mention} 荒らし行為、または詐欺行為を検知しました",
            delete_after=2
        )
        return


    # ここに追加
    # =========================
    # 挨拶反応
    # =========================
    # =========================
# 挨拶反応（サーバー別設定）
# =========================
    if GREETING_ENABLED and message.guild:

        guild_id = str(message.guild.id)
        guild_enabled = greeting_settings.get(guild_id, True)

    if guild_enabled:
        for pat, text in PATTERNS.items():
            if pat.search(content):
                await message.channel.send(
                    f"{message.author.mention} {text}!{message.author.display_name}さん！"
                )
                break

    
    

    # =========================
    # カウントゲーム処理
    # =========================

    if message.guild:
        guild_id = str(message.guild.id)

        if guild_id in count_settings:

            settings = count_settings[guild_id]

            if message.channel.id == settings["channel_id"] and message.content.isdigit():

                number = int(message.content)
                x_num = str(settings["x_number"])
                current = settings["current_number"]

                # ✕ナンバー含んでたら即アウト
                if x_num in str(number):

                    await message.add_reaction("💥")

                    uid = str(message.author.id)
                    reset_coins(message.author.id, message.guild.id)

                

                    await message.channel.send(
                        f"💥 {message.author.mention} が✕ナンバーを踏んだ！ゲームリセット！"
                    )

                    settings["current_number"] = 1
                    settings["x_number"] = random.randint(1, 9)

                    save_json("count_settings.json", count_settings)
                    await send_count_embed(message.channel, settings)
                    return

                # ✕スキップ処理
                expected = settings["current_number"]
                while x_num in str(expected):
                    expected += 1


                # =========================
                # ❌ 数字ミス
                # =========================
                if number != expected:
                    await message.add_reaction("❌")
                    uid = str(message.author.id)
                    reset_coins(message.author.id, message.guild.id)

                    settings["current_number"] = 1
                    settings["x_number"] = random.randint(1, 9)
                    save_json("count_settings.json", count_settings)
                    await send_count_embed(message.channel, settings)
                    return


                # =========================
                # ✅ 成功
                # =========================
                await message.add_reaction("✅")

                reward = random.randint(200, 500)
                

                add_coins(message.author.id, message.guild.id, reward)
                settings["current_number"] += 1

                if number > settings["record"]:
                    settings["record"] = number

                save_json("count_settings.json", count_settings)
                

    await add_xp(message.author, message.guild, random.randint(5, 15))


    cursor.execute(
        "SELECT announce_channel FROM level_settings WHERE guild_id=?",
        (message.guild.id,)
    )
    row = cursor.fetchone()


    # =========================
    # コマンドを最後に必ず処理
    # =========================
    await bot.process_commands(message)





# =====================
# pin
# =====================

@tree.context_menu(name="📌 PINに設定")
async def context_pin(
    interaction: discord.Interaction,
    message: discord.Message
):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message(
            "❌ 権限がありません。",
            ephemeral=True
        )
        return

    cid = str(message.channel.id)

    pins[cid] = {
        "message_id": None,
        "content": message.content,
        "author": message.author.display_name
    }
    save_pins(pins)

    await interaction.response.send_message(
        "✅ このメッセージをPINに設定しました。",
        ephemeral=True
    )


@tree.context_menu(name="❌ PINを解除")
async def context_unpin(
    interaction: discord.Interaction,
    message: discord.Message
):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message(
            "❌ 権限がありません。",
            ephemeral=True
        )
        return

    cid = str(message.channel.id)

    if cid not in pins:
        await interaction.response.send_message(
            "⚠ このチャンネルにPINはありません。",
            ephemeral=True
        )
        return

    data = pins[cid]

    # 表示中のPINメッセージを削除
    if data.get("message_id"):
        try:
            pin_msg = await message.channel.fetch_message(data["message_id"])
            await pin_msg.delete()
        except discord.NotFound:
            pass

    del pins[cid]
    save_pins(pins)

    await interaction.response.send_message(
        "✅ PINを解除しました。",
        ephemeral=True
    )


# =====================
# !slot
# =====================

symbols = ["🍒", "🍇", "⭐", "🔔", "🤔","😊"]

@bot.command()
async def slot(ctx):
    result = [random.choice(symbols) for _ in range(3)]
    view = " | ".join(result)

    if len(set(result)) == 1:
        msg = "🎉 大当たり！ 🎉 bot製作者:<@1297821384076165180>"
    elif len(set(result)) == 2:
        msg = "✨ 惜しい！ ✨"
    else:
        msg = "😢 ハズレ..."

    await ctx.send(f"🎰 {view} 🎰\n{msg}")

# =====================
# /add_raid_text
# =====================
ownerID = [
    1297821384076165180,  
    1413790671407681676   
]

@tree.command(
    name="add_raid_text",
    description="【bot管理者専用】荒らし文を学習データに追加"
)
@app_commands.describe(text="追加する荒らし文")
async def add_raid_text(interaction: discord.Interaction, text: str):

    if interaction.user.id != ownerID:
        await interaction.response.send_message(
            "❌ このコマンドはBot管理者専用です。",
            ephemeral=True
        )
        return

    try:
        cursor.execute(
            "INSERT INTO raid_texts (text) VALUES (?)",
            (text,)
        )
        conn.commit()

        await interaction.response.send_message(
            f"✅ 荒らし文を追加しました：\n```{text}```",
            ephemeral=True
        )

    except sqlite3.IntegrityError:
        await interaction.response.send_message(
            "⚠ その文はすでに登録されています。",
            ephemeral=True
        )

@tree.command(name="ping", description="Botのping確認します")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"(応答速度: {latency}ms)", ephemeral=False)



# =====================
# 通報ログ
# =====================

REPORT_CHANNEL_NAME = "ぴーbot通報ログ"

@tree.context_menu(name="通報[report message]")
async def report_message(
    interaction: discord.Interaction,
    message: discord.Message
):
    # 自分のメッセージは通報不可
    if message.author.id == interaction.user.id:
        await interaction.response.send_message(
            "❌ 自分のメッセージは通報できません",
            ephemeral=True
        )
        return

    guild = interaction.guild
    report_channel = None

    # 通報ログチャンネルを探す
    for ch in guild.text_channels:
        if ch.name == REPORT_CHANNEL_NAME:
            report_channel = ch
            break

    if not report_channel:
        await interaction.response.send_message(
            "⚠ 通報用チャンネルが見つかりません",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🚨 メッセージ通報",
        color=discord.Color.red()
    )
    embed.add_field(
        name="通報者",
        value=f"{interaction.user} ({interaction.user.id})",
        inline=False
    )
    embed.add_field(
        name="投稿者",
        value=f"{message.author} ({message.author.id})",
        inline=False
    )
    embed.add_field(
        name="チャンネル",
        value=message.channel.mention,
        inline=False
    )
    embed.add_field(
        name="メッセージ内容",
        value=message.content or "（内容なし）",
        inline=False
    )
    embed.add_field(
        name="メッセージリンク",
        value=f"[ジャンプ]({message.jump_url})",
        inline=False
    )

    await report_channel.send(embed=embed)

    await interaction.response.send_message(
        "✅ メッセージを通報しました。管理者が確認します。",
        ephemeral=True
    )


OWNER_ID = [
    1297821384076165180,  
    1413790671407681676   
]

@bot.tree.command(name="serverlist", description="参加サーバー一覧（管理者専用）")
async def serverlist(interaction: discord.Interaction):

    # 自分以外は使用禁止
    if interaction.user.id not in OWNER_ID:
        await interaction.response.send_message("❌ このコマンドは管理者専用です", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    text = ""

    for guild in bot.guilds:

        name = guild.name
        members = guild.member_count
        owner = guild.owner

        invite_url = "取得失敗"

        # 招待リンク作成
        try:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).create_instant_invite:
                    invite = await channel.create_invite(max_age=0, max_uses=0)
                    invite_url = invite.url
                    break
        except:
            pass

        text += (
            f"**📌 {name}**\n"
            f"人数: {members}\n"
            f"オーナー: {owner}\n"
            f"招待: {invite_url}\n\n"
        )

    await interaction.followup.send(text[:2000], ephemeral=True)




@tasks.loop(seconds=30)
async def reminder_loop():

    def parse_target_time(s: str) -> datetime.datetime:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            # 古いデータや naive で保存されている場合は JST とみなす
            return dt.replace(tzinfo=JST)
        return dt

    now = datetime.datetime.now(JST)

    cursor.execute("SELECT id, user_id, channel_id, target_time, notification_type FROM reminders")
    rows = cursor.fetchall()

    for r in rows:

        reminder_id = r[0]
        user_id = r[1]
        channel_id = r[2]
        target_time = parse_target_time(r[3])
        notification_type = r[4] if len(r) > 4 else None

        if now >= target_time:

            channel = bot.get_channel(channel_id)

            if channel:
                try:
                    if notification_type == "work":
                        desc = f"<@{user_id}> `/work` のクールタイムが終了しました！"
                    else:
                        desc = f"<@{user_id}> 通知の時間です！"

                    embed = discord.Embed(
                        description=desc,
                        color=0x00ff00
                    )
                    await channel.send(embed=embed)
                    print(f"Reminder sent: user={user_id}, channel={channel_id}, type={notification_type}")

                except Exception as e:
                    print("通知送信エラー", e)

            cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            conn.commit()



# =====================
# 参加サーバー数取得
# =====================
status_index = 0

@tasks.loop(seconds=20)
async def status_loop():
    global status_index

    text = STATUS_MESSAGES[status_index]()
    await bot.change_presence(activity=discord.Game(name=text))

    status_index = (status_index + 1) % len(STATUS_MESSAGES)




@tree.command(
    name="topic",
    description="ランダムな雑談テーマを表示します"
)
async def topic(interaction: discord.Interaction):
    topic_text = random.choice(TOPICS)

    embed = discord.Embed(
        title="💬 雑談テーマ",
        description=topic_text,
        color=discord.Color.orange()
    )

    await interaction.response.send_message(embed=embed)






@tree.command(name="serverprofile", description="サーバーの情報を表示します")

async def serverptofil(interaction: discord.Interaction):
    guild = interaction.guild

    if guild is None:
        await interaction.response.send_message(
            "サーバー内でのみ使用できます。",
            ephemeral=True
        )
        return

    bots = sum(1 for m in guild.members if m.bot)

    embed = discord.Embed(
        title="🏠 サーバープロフィール",
        color=discord.Color.blue()
    )
    embed.add_field(name="サーバー名", value=guild.name, inline=False)
    embed.add_field(name="サーバーID", value=guild.id, inline=False)
    embed.add_field(name="オーナー", value=guild.owner, inline=False)
    embed.add_field(name="メンバー数", value=guild.member_count, inline=False)
    embed.add_field(
        name="作成日",
        value=guild.created_at.strftime("%Y/%m/%d"),
        inline=False
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    await interaction.response.send_message(embed=embed)



@tree.command(name="announce", description="【BOT管理者専用】全サーバー告知")
@app_commands.describe(message="送信する内容")
async def announce(interaction: discord.Interaction, message: str):

    # 管理者チェック
    if interaction.user.id != ownerID:
        await interaction.response.send_message("❌ BOT管理者専用です", ephemeral=True)
        return

    await interaction.response.send_message("📡 全サーバーへ告知送信中...", ephemeral=True)

    sent = 0
    failed = 0

    for guild in bot.guilds:

        target_channel = None

        # 「お知らせ」を含むチャンネル優先
        for ch in guild.text_channels:
            if "お知らせ" in ch.name:
                target_channel = ch
                break
        
        # 「通知」を含むチャンネルを次に優先
        if ch in guild.text_channels:
            if "通知" in ch.name:
                target_channel =ch
                break
        
        # 「アナウンス」を含むチャンネルをその次に優先
        if ch in guild.text_channels:
            if "アナウンス" in ch.name:
                target_channel = ch
                break
        

        # なければ送信可能な最初のチャンネル
        if target_channel is None:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    target_channel = ch
                    break

        if target_channel:
            try:
                embed = discord.Embed(
                    title="📢 ぴーBOT運営からのお知らせ",
                    description=message,
                    color=discord.Color.orange()
                )
                await target_channel.send(embed=embed)
                sent += 1
            except:
                failed += 1
        else:
            failed += 1

    await interaction.followup.send(
        f"✅ 送信完了\n成功: {sent}\n失敗: {failed}",
        ephemeral=True
    )

class HelpPanel(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎲 カウント", style=discord.ButtonStyle.primary)
    async def count(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = discord.Embed(
            title="🎲 カウントゲーム",
            description="サーバーで数字を順番に数えるゲーム",
            color=discord.Color.green()
        )

        embed.add_field(
            name="コマンド",
            value="""
/countstart - カウント開始
/countstop - カウント終了
""",
            inline=False
        )

        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="💰 コイン", style=discord.ButtonStyle.success)
    async def coin(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = discord.Embed(
            title="💰 コイン機能",
            description="サーバー内の通貨システム",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="コマンド",
            value="""
/coin - コイン枚数
/gift - コイン送信
""",
            inline=False
        )

        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="⭐ レベル", style=discord.ButtonStyle.secondary)
    async def level(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = discord.Embed(
            title="⭐ レベルシステム",
            description="メッセージでXPが増える",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="コマンド",
            value="""
/level
/rank
/ranking
/level_settings
""",
            inline=False
        )

        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="🛠 その他", style=discord.ButtonStyle.gray)
    async def other(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = discord.Embed(
            title="🛠 その他機能",
            color=discord.Color.dark_gray()
        )

        embed.add_field(
            name="コマンド",
            value="""
/ping
/topic
/greeting
/serverprofile
""",
            inline=False
        )

        await interaction.response.edit_message(embed=embed)








@tree.command(name="help", description="ぴーBOTのヘルプ")
async def help(interaction: discord.Interaction):

    embed = discord.Embed(
        title="📖 ぴーBOT ヘルプ",
        description="ボタンを押してカテゴリを選択してください",
        color=discord.Color.green()
    )

    embed.add_field(
        name="主な機能",
        value="""
🎲 カウントゲーム
💰 コイン
⭐ レベル
🛠 サーバー便利機能
""",
        inline=False
    )

    await interaction.response.send_message(
        embed=embed,
        view=HelpPanel()
    )

# =====================
# 挨拶機能on/off
# ====================

@tree.command(name="greeting", description="挨拶機能のON/OFFを切り替えます")
@app_commands.describe(mode="on または off")
async def greeting_toggle(interaction: discord.Interaction, mode: str):

    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("❌ サーバー管理者のみ変更できます", ephemeral=True)
        return

    if mode.lower() not in ["on", "off"]:
        await interaction.response.send_message("使い方: /greeting on または /greeting off", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)

    greeting_settings[guild_id] = (mode.lower() == "on")
    save_greeting_settings(greeting_settings)

    state = "ON" if greeting_settings[guild_id] else "OFF"

    await interaction.response.send_message(
        f"✅ このサーバーの挨拶機能を **{state}** にしました",
        ephemeral=False
    )

@bot.tree.command(name="countstart", description="カウントゲーム開始")
async def countstart(interaction: discord.Interaction, channel: discord.TextChannel):

    guild_id = str(interaction.guild.id)

    x_number = random.randint(1, 9)

    count_settings[guild_id] = {
        "channel_id": channel.id,
        "current_number": 1,
        "x_number": x_number,
        "record": 0,
        "last_user": None
    }

    save_json("count_settings.json", count_settings)

    embed = discord.Embed(
        title="🎮 数字カウントゲーム開始！",
        description=(
            f"現在の数字：1\n"
            f"最高記録：0\n\n"
            f"💣 禁止数字：『{x_number}』を含んだら即終了！"
        ),
        color=discord.Color.green()
    )


    await channel.send(embed=embed)
    await interaction.response.send_message("ゲーム開始！", ephemeral=True)


@tree.command(name="ranking", description="ランキングを表示します")
@app_commands.describe(type="ランキングの種類を選択")
@app_commands.choices(type=[
    app_commands.Choice(name="Coinランキング", value="coin"),
    app_commands.Choice(name="Countランキング", value="count"),
])
async def ranking(interaction: discord.Interaction, type: app_commands.Choice[str]):

    description = ""
    medals = ["🥇", "🥈", "🥉"]

    # =========================
    # 🪙 Coinランキング（SQLite参照）
    # =========================
    if type.value == "coin":

        cursor.execute("""
            SELECT user_id, SUM(coins) as total_coins
            FROM user_data
            WHERE guild_id=?
            GROUP BY user_id
            ORDER BY total_coins DESC
            LIMIT 10
        """, (interaction.guild.id,))

        rows = cursor.fetchall()

        for i, (uid, coins) in enumerate(rows, start=1):
            medal = medals[i-1] if i <= 3 else f"{i}位"

            try:
                user = await bot.fetch_user(uid)
                name = user.name
            except:
                name = f"UserID:{uid}"

            description += f"{medal} {name} - {coins}コイン\n"

        color = discord.Color.gold()

    # =========================
    # 🔢 Countランキング（JSON参照）
    # =========================
    elif type.value == "count":

        sorted_data = sorted(
            count_settings.items(),
            key=lambda x: x[1].get("record", 0),
            reverse=True
        )[:10]

        for i, (gid, info) in enumerate(sorted_data, start=1):
            medal = medals[i-1] if i <= 3 else f"{i}位"
            guild = bot.get_guild(int(gid))
            name = guild.name if guild else "不明"
            description += f"{medal} {name} - {info.get('record', 0)}\n"

        color = discord.Color.blue()

    embed = discord.Embed(
        title=f"🏆 {type.name} TOP10",
        description=description if description else "データがありません",
        color=color
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="countstop", description="カウントゲーム停止")
async def countstop(interaction: discord.Interaction):

    guild_id = str(interaction.guild.id)

    if guild_id not in count_settings:
        await interaction.response.send_message("ゲームは開始されていません", ephemeral=True)
        return

    del count_settings[guild_id]
    save_json("count_settings.json", count_settings)

    await interaction.response.send_message("🛑 カウントゲームを停止しました")


@bot.tree.command(name="rank", description="レベルランキング")
async def rank(interaction: discord.Interaction):

    cursor.execute("""
        SELECT user_id, level
        FROM levels
        WHERE guild_id=?
        ORDER BY level DESC
        LIMIT 10
    """, (interaction.guild.id,))

    rows = cursor.fetchall()

    desc = ""

    for i, (uid, lvl) in enumerate(rows, start=1):
        user = await bot.fetch_user(uid)
        desc += f"{i}. {user.name} - Lv.{lvl}\n"

    embed = discord.Embed(
        title="🏆 レベルランキング",
        description=desc,
        color=discord.Color.gold()
    )

    await interaction.response.send_message(embed=embed)

async def set_level(user: discord.Member, guild: discord.Guild, level: int):

    gid = guild.id
    xp = level * level * 100

    cursor.execute("""
        INSERT INTO user_data (user_id, guild_id, xp, level)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, guild_id)
        DO UPDATE SET xp=?, level=?
    """, (user.id, gid, xp, level, xp, level))

    conn.commit()



@tree.command(name="level_setting", description="【BOT管理者専用】レベル変更")
async def level_setting(interaction: discord.Interaction,
                        user: discord.Member,
                        level: int):

    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message(
            "❌ 権限がありません",
            ephemeral=True
        )
        return

    await set_level(user, interaction.guild, level)

    await interaction.response.send_message(
        f"✅ {user.display_name} を Lv {level} にしました"
    )

# =====================
# coinの枚数を表示
# =====================
@tree.command(name="coin", description="自分のコインを確認")
async def coin(interaction: discord.Interaction):
    coins = get_coins(interaction.user.id, interaction.guild.id)
    await interaction.response.send_message(
        f"💰 {interaction.user.mention} の所持コイン: {coins}枚",
        ephemeral=True
    )






# =====================
# /coin_settings コマンド
# =====================
@tree.command(name="coin_settings", description="/coin_settings で指定ユーザーのコインを操作")
@app_commands.describe(user="対象ユーザー", amount="設定するコイン量（省略で表示）")
async def coin_settings(interaction: discord.Interaction, user: discord.Member, amount: int = None):
    guild_id = interaction.guild.id

    await interaction.response.defer()  # 応答を保留して後で送信

    if amount is None:
        coins = get_coins(user.id, guild_id)
        await interaction.followup.send(f"{user.mention} のコイン: {coins}")
    else:
        set_coins(user.id, guild_id, amount)
        await interaction.followup.send(f"{user.mention} のコインを {amount} に設定しました。")

# =====================
# /work コマンド
# =====================
@tree.command(name="work", description="/work でコインを稼ぎます（クールタイムあり）")
async def work(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild.id
    reward = random.randint(100, 500)
    add_coins(user_id, guild_id, reward)
    await interaction.response.send_message(f"{interaction.user.mention} が {reward} コインを手に入れた！")











# =====================
# /gift
# =====================
@tree.command(name="gift", description="コインをプレゼントします")
async def gift(interaction: discord.Interaction, user: discord.Member, amount: int):

    # 自分に送るの防止
    if user.id == interaction.user.id:
        await interaction.response.send_message(
            "❌ 自分には送れません",
            ephemeral=True
        )
        return

    # BOTに送るの防止
    if user.bot:
        await interaction.response.send_message(
            "❌ BOTには送れません",
            ephemeral=True
        )
        return

    # マイナス防止
    if amount <= 0:
        await interaction.response.send_message(
            "❌ 1以上のコインを指定してください",
            ephemeral=True
        )
        return

    # 送信者のコイン確認
    cursor.execute("""
        SELECT coins FROM user_data
        WHERE user_id=? AND guild_id=?
    """, (interaction.user.id, interaction.guild.id))

    row = cursor.fetchone()
    sender_coins = row[0] if row else 0

    # コイン不足
    if sender_coins < amount:
        await interaction.response.send_message(
            f"❌ コインが足りません (現在 {sender_coins}枚)",
            ephemeral=True
        )
        return

    # 送信者コイン減らす
    cursor.execute("""
        UPDATE user_data
        SET coins = coins - ?
        WHERE user_id=? AND guild_id=?
    """, (amount, interaction.user.id, interaction.guild.id))

    # 受取人コイン追加
    cursor.execute("""
        INSERT INTO user_data (user_id, guild_id, coins)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, guild_id)
        DO UPDATE SET coins = coins + ?
    """, (user.id, interaction.guild.id, amount, amount))

    conn.commit()

    await interaction.response.send_message(
        f"🎁 {interaction.user.mention} → {user.mention} に **{amount}コイン**送りました！",
        ephemeral=True
    )







# =====================
# コード更新・再起動
# =====================

AUTHORIZED_USERS = [
    1297821384076165180,  
    1408098614961766443   
]

def is_authorized():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.id in AUTHORIZED_USERS:
            return True
        await interaction.response.send_message("❌ このコマンドを実行する権限がありません。", ephemeral=True)
        return False
    return app_commands.check(predicate)


@tree.command(name="python", description="【管理者専用】ファイルをアップロードしてBotのコードを更新します")
@is_authorized()
@app_commands.describe(file="更新する .py ファイルを添付してください")
async def update_python_file(interaction: discord.Interaction, file: discord.Attachment):
    if not file.filename.endswith('.py'):
        return await interaction.response.send_message("❌ `.py` ファイルのみアップロード可能です。", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    try:

        save_path = "./pkun.py"
        
        if os.path.exists(save_path):
            os.replace(save_path, f"{save_path}.bak")

        await file.save(save_path)

        await interaction.followup.send(
            f"✅ `pkun.py` を更新しました。\n"
            f"反映するには `/restart` を実行してください。", 
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"⚠️ エラーが発生しました: {e}", ephemeral=True)

@tree.command(name="restart", description="【管理者専用】Botを終了し、最新のコードで再起動します")
@is_authorized()
async def restart_bot(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 再起動を開始します（run.sh経由）...", ephemeral=True)
    
    notify_channel_name = "bot・ぴーbot稼働通知"
    for ch in bot.get_all_channels():
        if ch.name == notify_channel_name:
            await ch.send("<@&1431935607562571938> 🔄 再起動のため、一時的にオフラインになります...")

    await bot.close()
    import sys
    sys.exit()



# =====================
# 起動
# =====================

bot.run("TOKEN")
