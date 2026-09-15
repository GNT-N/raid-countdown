import asyncio
import math
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv


# ============================================================
# APPLICATION DIRECTORY
# ============================================================

if getattr(sys, "frozen", False):
    # Compiled .exe version
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    # Normal Python version
    BASE_DIR = Path(__file__).resolve().parent


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID_RAW = os.getenv("GUILD_ID")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing from the .env file."
    )

if not GUILD_ID_RAW:
    raise RuntimeError(
        "GUILD_ID is missing from the .env file."
    )

GUILD_ID = int(GUILD_ID_RAW)

DATABASE_FILE = BASE_DIR / "raids.db"

# raid_id -> asyncio.Task
running_tasks = {}


# ============================================================
# USER PERMISSIONS
# ============================================================

def can_manage_raids(
    interaction: discord.Interaction
) -> bool:
    """
    Allows members with the Discord
    'Manage Server' permission.
    """

    if not isinstance(
        interaction.user,
        discord.Member
    ):
        return False

    return (
        interaction.user
        .guild_permissions
        .manage_guild
    )


# ============================================================
# SQLITE DATABASE
# ============================================================

def init_database():

    with sqlite3.connect(DATABASE_FILE) as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS raids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            )
        """)

        db.commit()


def save_raid(
    guild_id: int,
    channel_id: int,
    message_id: int,
    title: str,
    timestamp: int
) -> int:

    with sqlite3.connect(DATABASE_FILE) as db:

        cursor = db.execute(
            """
            INSERT INTO raids (
                guild_id,
                channel_id,
                message_id,
                title,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                channel_id,
                message_id,
                title,
                timestamp
            )
        )

        db.commit()

        return cursor.lastrowid


def delete_raid_from_database(
    raid_id: int
):

    with sqlite3.connect(DATABASE_FILE) as db:

        db.execute(
            "DELETE FROM raids WHERE id = ?",
            (raid_id,)
        )

        db.commit()


def get_raid(
    raid_id: int
):

    with sqlite3.connect(DATABASE_FILE) as db:

        cursor = db.execute(
            """
            SELECT
                id,
                guild_id,
                channel_id,
                message_id,
                title,
                timestamp
            FROM raids
            WHERE id = ?
            """,
            (raid_id,)
        )

        return cursor.fetchone()


def get_guild_raids(
    guild_id: int
):

    with sqlite3.connect(DATABASE_FILE) as db:

        cursor = db.execute(
            """
            SELECT
                id,
                title,
                timestamp
            FROM raids
            WHERE guild_id = ?
            AND timestamp > ?
            ORDER BY timestamp ASC
            """,
            (
                guild_id,
                int(time.time())
            )
        )

        return cursor.fetchall()


def get_all_active_raids():

    with sqlite3.connect(DATABASE_FILE) as db:

        cursor = db.execute(
            """
            SELECT
                id,
                guild_id,
                channel_id,
                message_id,
                title,
                timestamp
            FROM raids
            WHERE timestamp > ?
            """,
            (
                int(time.time()),
            )
        )

        return cursor.fetchall()


def clean_old_raids():

    with sqlite3.connect(DATABASE_FILE) as db:

        db.execute(
            "DELETE FROM raids WHERE timestamp <= ?",
            (
                int(time.time()),
            )
        )

        db.commit()


# ============================================================
# DISPLAY
# ============================================================

def format_remaining(
    seconds: int
) -> str:

    seconds = max(
        0,
        seconds
    )

    days, remaining = divmod(
        seconds,
        86400
    )

    hours, remaining = divmod(
        remaining,
        3600
    )

    minutes, seconds = divmod(
        remaining,
        60
    )

    return (
        f"{days:02d}d "
        f"{hours:02d}h "
        f"{minutes:02d}m "
        f"{seconds:02d}s"
    )


def create_raid_embed(
    title: str,
    timestamp: int
) -> discord.Embed:

    remaining_seconds = max(
        0,
        math.ceil(
            timestamp - time.time()
        )
    )

    return discord.Embed(
        title=f"⚔️ {title}",
        description=(
            f"📅 **Raid date:** "
            f"<t:{timestamp}:F>\n"

            f"🕒 **Starts:** "
            f"<t:{timestamp}:R>\n\n"

            f"⏳ **Time remaining**\n"

            f"# `"
            f"{format_remaining(remaining_seconds)}"
            f"`"
        )
    )


def create_finished_embed(
    title: str,
    timestamp: int
) -> discord.Embed:

    return discord.Embed(
        title=f"⚔️ {title}",
        description=(
            "# 🔥 THE RAID STARTS NOW!\n\n"
            f"📅 <t:{timestamp}:F>"
        )
    )


# ============================================================
# COUNTDOWN
# ============================================================

async def countdown(
    raid_id: int,
    message: discord.Message,
    title: str,
    timestamp: int
):

    try:

        while True:

            remaining_seconds = math.ceil(
                timestamp - time.time()
            )

            # =================================================
            # RAID STARTED
            # =================================================

            if remaining_seconds <= 0:

                try:

                    await message.edit(
                        embed=create_finished_embed(
                            title,
                            timestamp
                        )
                    )

                except discord.HTTPException:
                    pass

                delete_raid_from_database(
                    raid_id
                )

                return


            # =================================================
            # COUNTDOWN UPDATE
            # =================================================

            try:

                await message.edit(
                    embed=create_raid_embed(
                        title,
                        timestamp
                    )
                )


            except discord.NotFound:

                # The message was manually deleted.

                delete_raid_from_database(
                    raid_id
                )

                return


            except discord.Forbidden:

                print(
                    f"⚠️ No longer able to access "
                    f"raid #{raid_id}."
                )

                return


            except discord.HTTPException as error:

                print(
                    f"⚠️ Discord error for "
                    f"raid #{raid_id}: {error}"
                )

                await asyncio.sleep(2)

                continue


            # =================================================
            # NEXT SECOND
            # =================================================

            await asyncio.sleep(1)


    except asyncio.CancelledError:

        # Normal behavior when /raid delete
        # stops the countdown.

        return


    finally:

        running_tasks.pop(
            raid_id,
            None
        )


# ============================================================
# BOT
# ============================================================

class RaidBot(discord.Client):

    def __init__(self):

        super().__init__(
            intents=discord.Intents.default()
        )

        self.tree = app_commands.CommandTree(
            self
        )

        self.raids_restored = False


    async def setup_hook(self):

        guild = discord.Object(
            id=GUILD_ID
        )

        self.tree.copy_global_to(
            guild=guild
        )

        await self.tree.sync(
            guild=guild
        )

        print(
            "✅ Commands synchronized."
        )


bot = RaidBot()


# ============================================================
# /raid COMMAND GROUP
# ============================================================

raid_group = app_commands.Group(
    name="raid",
    description="Raid countdown management"
)


# ============================================================
# /raid create
# ============================================================

@raid_group.command(
    name="create",
    description="Create a new raid countdown"
)
@app_commands.describe(
    title="Example: Dungeon 1",
    date="Format: DD/MM/YYYY",
    time="Format: HH:MM"
)
async def raid_create(
    interaction: discord.Interaction,
    title: str,
    date: str,
    time: str
):

    # ========================================================
    # USER PERMISSION
    # ========================================================

    if not can_manage_raids(
        interaction
    ):

        await interaction.response.send_message(
            "❌ You do not have permission "
            "to create a raid.\n\n"
            "You need the **Manage Server** permission.",
            ephemeral=True
        )

        return


    # ========================================================
    # BOT PERMISSIONS
    # ========================================================

    permissions = interaction.app_permissions

    if not (
        permissions.view_channel
        and permissions.send_messages
        and permissions.embed_links
        and permissions.read_message_history
    ):

        await interaction.response.send_message(
            "❌ I am missing permissions "
            "in this channel.\n\n"

            "I need:\n"
            "• View Channel\n"
            "• Send Messages\n"
            "• Embed Links\n"
            "• Read Message History",

            ephemeral=True
        )

        return


    # ========================================================
    # DATE / TIME VALIDATION
    # ========================================================

    try:

        target = datetime.strptime(
            f"{date} {time}",
            "%d/%m/%Y %H:%M"
        )

        # Uses the local timezone of the machine
        # running the bot.

        timestamp = int(
            target.timestamp()
        )


    except ValueError:

        await interaction.response.send_message(
            "❌ Invalid date or time format.\n\n"

            "Example:\n"
            "`date: 20/08/2026`\n"
            "`time: 20:00`",

            ephemeral=True
        )

        return


    # ========================================================
    # FUTURE DATE?
    # ========================================================

    if timestamp <= int(
        time_module()
    ):

        await interaction.response.send_message(
            "❌ The raid date must be in the future.",
            ephemeral=True
        )

        return


    # ========================================================
    # CHANNEL
    # ========================================================

    channel = interaction.channel

    if channel is None:

        await interaction.response.send_message(
            "❌ Unable to access this channel.",
            ephemeral=True
        )

        return


    # ========================================================
    # PROCESSING
    # ========================================================

    await interaction.response.defer(
        ephemeral=True
    )


    # ========================================================
    # CREATE PUBLIC MESSAGE
    # ========================================================

    try:

        message = await channel.send(
            "⏳ Creating raid..."
        )


    except discord.Forbidden:

        await interaction.followup.send(
            "❌ I do not have permission "
            "to send messages in this channel.",
            ephemeral=True
        )

        return


    except discord.HTTPException:

        await interaction.followup.send(
            "❌ Discord encountered an error "
            "while creating the raid.",
            ephemeral=True
        )

        return


    # ========================================================
    # SAVE TO SQLITE
    # ========================================================

    raid_id = save_raid(
        guild_id=interaction.guild_id,
        channel_id=channel.id,
        message_id=message.id,
        title=title,
        timestamp=timestamp
    )


    # ========================================================
    # DISPLAY RAID
    # ========================================================

    try:

        await message.edit(
            content=None,
            embed=create_raid_embed(
                title,
                timestamp
            )
        )


    except discord.HTTPException:

        delete_raid_from_database(
            raid_id
        )

        try:

            await message.delete()

        except discord.HTTPException:

            pass

        await interaction.followup.send(
            "❌ Unable to display the countdown.",
            ephemeral=True
        )

        return


    # ========================================================
    # START COUNTDOWN
    # ========================================================

    task = asyncio.create_task(
        countdown(
            raid_id,
            message,
            title,
            timestamp
        )
    )

    running_tasks[
        raid_id
    ] = task


    # ========================================================
    # PRIVATE CONFIRMATION
    # ========================================================

    await interaction.followup.send(
        f"✅ Raid **#{raid_id} — {title}** created.",
        ephemeral=True
    )


# ============================================================
# /raid list
# ============================================================

@raid_group.command(
    name="list",
    description="Show all scheduled raids"
)
async def raid_list(
    interaction: discord.Interaction
):

    raids = get_guild_raids(
        interaction.guild_id
    )


    if not raids:

        await interaction.response.send_message(
            "📭 No raids are currently scheduled.",
            ephemeral=True
        )

        return


    lines = []


    for raid_id, title, timestamp in raids:

        lines.append(
            f"**#{raid_id} — {title}**\n"
            f"📅 <t:{timestamp}:F>\n"
            f"⏳ <t:{timestamp}:R>"
        )


    embed = discord.Embed(
        title="⚔️ Scheduled Raids",
        description="\n\n".join(
            lines
        )
    )


    await interaction.response.send_message(
        embed=embed,
        ephemeral=True
    )


# ============================================================
# /raid delete
# ============================================================

@raid_group.command(
    name="delete",
    description="Delete a scheduled raid"
)
@app_commands.describe(
    raid_id="Raid ID"
)
async def raid_delete(
    interaction: discord.Interaction,
    raid_id: int
):

    # ========================================================
    # USER PERMISSION
    # ========================================================

    if not can_manage_raids(
        interaction
    ):

        await interaction.response.send_message(
            "❌ You do not have permission "
            "to delete a raid.\n\n"
            "You need the **Manage Server** permission.",
            ephemeral=True
        )

        return


    # ========================================================
    # GET RAID
    # ========================================================

    raid = get_raid(
        raid_id
    )


    if raid is None:

        await interaction.response.send_message(
            "❌ This raid does not exist.",
            ephemeral=True
        )

        return


    (
        _,
        guild_id,
        channel_id,
        message_id,
        title,
        timestamp
    ) = raid


    # ========================================================
    # SERVER CHECK
    # ========================================================

    if guild_id != interaction.guild_id:

        await interaction.response.send_message(
            "❌ This raid does not belong "
            "to this server.",
            ephemeral=True
        )

        return


    # ========================================================
    # STOP COUNTDOWN
    # ========================================================

    task = running_tasks.get(
        raid_id
    )


    if task:

        task.cancel()


    # ========================================================
    # DELETE DISCORD MESSAGE
    # ========================================================

    try:

        channel = bot.get_channel(
            channel_id
        )


        if channel is None:

            channel = await bot.fetch_channel(
                channel_id
            )


        message = await channel.fetch_message(
            message_id
        )


        await message.delete()


    except (
        discord.NotFound,
        discord.Forbidden,
        discord.HTTPException
    ):

        pass


    # ========================================================
    # DELETE FROM SQLITE
    # ========================================================

    delete_raid_from_database(
        raid_id
    )


    # ========================================================
    # CONFIRMATION
    # ========================================================

    await interaction.response.send_message(
        f"✅ Raid **#{raid_id} — {title}** deleted.",
        ephemeral=True
    )


# ============================================================
# ADD /raid GROUP
# ============================================================

bot.tree.add_command(
    raid_group
)


# ============================================================
# RESTORE RAIDS AFTER RESTART
# ============================================================

async def restore_raids():

    clean_old_raids()

    raids = get_all_active_raids()


    if not raids:

        print(
            "ℹ️ No raids to restore."
        )

        return


    print(
        f"🔄 Restoring "
        f"{len(raids)} raid(s)..."
    )


    for raid in raids:

        (
            raid_id,
            guild_id,
            channel_id,
            message_id,
            title,
            timestamp
        ) = raid


        try:

            channel = bot.get_channel(
                channel_id
            )


            if channel is None:

                channel = await bot.fetch_channel(
                    channel_id
                )


            message = await channel.fetch_message(
                message_id
            )


            task = asyncio.create_task(
                countdown(
                    raid_id,
                    message,
                    title,
                    timestamp
                )
            )


            running_tasks[
                raid_id
            ] = task


            print(
                f"✅ Raid #{raid_id} restored."
            )


        except discord.NotFound:

            delete_raid_from_database(
                raid_id
            )


        except discord.Forbidden:

            print(
                f"⚠️ Access denied for "
                f"raid #{raid_id}."
            )


        except discord.HTTPException as error:

            print(
                f"⚠️ Unable to restore "
                f"raid #{raid_id}: {error}"
            )


# ============================================================
# EVENTS
# ============================================================

@bot.event
async def on_ready():

    print(
        f"✅ Connected as {bot.user}"
    )


    if not bot.raids_restored:

        bot.raids_restored = True

        await restore_raids()


# ============================================================
# SMALL HELPER
# ============================================================

def time_module():
    """
    Avoids conflict between the imported
    time module and the /raid create
    parameter named 'time'.
    """

    return time.time()


# ============================================================
# INITIALIZATION
# ============================================================

print(
    f"📁 Application directory: "
    f"{BASE_DIR}"
)

print(
    f"💾 Database: "
    f"{DATABASE_FILE}"
)

init_database()

bot.run(TOKEN)