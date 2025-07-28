import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from datetime import datetime
import json
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
CONFIG_FILE = "like_channels.json"

class LikeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_host = "   "
        self.config_data = self.load_config()
        self.cooldowns = {}
        self.session = aiohttp.ClientSession()

        self.headers = {}
        if RAPIDAPI_KEY:
            self.headers = {
                'x-rapidapi-key': RAPIDAPI_KEY,
                'x-rapidapi-host': "free-fire-like1.p.rapidapi.com"
            }

    def load_config(self):
        default_config = {
            "servers": {}
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded_config = json.load(f)
                    loaded_config.setdefault("servers", {})
                    return loaded_config
            except json.JSONDecodeError:
                print(f"WARNING: The configuration file '{CONFIG_FILE}' is corrupt or empty. Resetting to default configuration.")
        self.save_config(default_config)
        return default_config

    def save_config(self, config_to_save=None):
        data_to_save = config_to_save if config_to_save is not None else self.config_data
        temp_file = CONFIG_FILE + ".tmp"
        with open(temp_file, 'w') as f:
            json.dump(data_to_save, f, indent=4)
        os.replace(temp_file, CONFIG_FILE)

    async def check_channel(self, ctx):
        if ctx.guild is None:
            return True
        guild_id = str(ctx.guild.id)
        like_channels = self.config_data["servers"].get(guild_id, {}).get("like_channels", [])
        return not like_channels or str(ctx.channel.id) in like_channels

    async def cog_load(self):
        pass

    @commands.hybrid_command(name="setlikechannel", description="✅ Allow the /like command in a channel.", with_app_command=True)
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="The channel to allow the /like command in.")
    async def set_like_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        server_config = self.config_data["servers"].setdefault(guild_id, {})
        like_channels = server_config.setdefault("like_channels", [])

        channel_id_str = str(channel.id)

        if channel_id_str in like_channels:
            await ctx.send(f"⚠️ {channel.mention} is already allowed for /like.", ephemeral=True)
        else:
            like_channels.append(channel_id_str)
            self.save_config()
            await ctx.send(f"✅ {channel.mention} has been added to allowed /like channels.", ephemeral=True)


    @commands.hybrid_command(name="removelikechannel", description="❌ Disallow the /like command in a channel.", with_app_command=True)
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="The channel to disallow the /like command in.")
    async def remove_like_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        server_config = self.config_data["servers"].setdefault(guild_id, {})
        like_channels = server_config.setdefault("like_channels", [])

        channel_id_str = str(channel.id)

        if channel_id_str in like_channels:
            like_channels.remove(channel_id_str)
            self.save_config()
            await ctx.send(f"❌ {channel.mention} has been removed from allowed /like channels.", ephemeral=True)
        else:
            await ctx.send(f"⚠️ {channel.mention} was not in the list of allowed channels.", ephemeral=True)


    @commands.hybrid_command(name="likechannels", description="📜 List allowed channels for the /like command.", with_app_command=True)
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def list_like_channels(self, ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        server_config = self.config_data["servers"].get(guild_id, {})
        like_channels = server_config.get("like_channels", [])

        if not like_channels:
            await ctx.send("ℹ️ No channels are restricted — `/like` is allowed everywhere.", ephemeral=True)
            return

        mentions = []
        for channel_id in like_channels:
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                mentions.append(channel.mention)
            else:
                mentions.append(f"<#{channel_id}>")

        channels_list = "\n".join(mentions)
        await ctx.send(f"✅ `/like` is allowed in the following channels:\n{channels_list}", ephemeral=True)


    @commands.hybrid_command(name="like", description="Sends likes to a Free Fire player")
    @app_commands.describe(uid="Player UID (numbers only, minimum 6 characters)")
    async def like_command(self, ctx: commands.Context, uid: str):
        is_slash = ctx.interaction is not None

        if not await self.check_channel(ctx):
            guild_id = str(ctx.guild.id)
            allowed_ids = self.config_data["servers"].get(guild_id, {}).get("like_channels", [])

            if allowed_ids:
                allowed_mentions = ", ".join(f"<#{ch_id}>" for ch_id in allowed_ids)
                msg = (
                    "🚫 This command is **not allowed** in this channel.\n"
                    f"✅ You can use it in: {allowed_mentions}"
            )
            else:
                msg = "🚫 This command is **not allowed** in this channel and no allowed channels are configured."

            if hasattr(ctx, "response") and not ctx.response.is_done():
                await ctx.response.send_message(msg, ephemeral=True)
            else:
                await ctx.reply(msg, mention_author=False,ephemeral=True)
            return


        user_id = ctx.author.id
        cooldown = 30
        if user_id in self.cooldowns:
            last_used = self.cooldowns[user_id]
            remaining = cooldown - (datetime.now() - last_used).seconds
            if remaining > 0:
                await ctx.send(f"Please wait {remaining} seconds before using this command again.", ephemeral=is_slash)
                return
        self.cooldowns[user_id] = datetime.now()

        if not uid.isdigit() or len(uid) < 6:
            await ctx.reply("Invalid UID. It must contain only numbers and be at least 6 characters long.", mention_author=False, ephemeral=is_slash)
            return


        try:
            async with ctx.typing():
                async with self.session.get(f"{self.api_host}/like?uid={uid}", headers=self.headers) as response:
                    if response.status == 404:
                        await self._send_player_not_found(ctx, uid)
                        return
                    # if response.status ==429 :
                        # await self._send_api_limit_reached
                    if response.status != 200:
                        print(f"API Error: {response.status} - {await response.text()}")
                        await self._send_api_error(ctx)
                        return

                    data = await response.json()
                    embed = discord.Embed(
                        title="FREE FIRE LIKE",
                        color=0x2ECC71 if data.get("status") == 1 else 0xE74C3C,
                        timestamp=datetime.now()
                    )

                    if data.get("status") == 1:
                        embed.description = (
                            f"```\n"
                            f"┌  ACCOUNT\n"
                            f"├─ NICKNAME: {data.get('nickname', 'Unknown')}\n"
                            f"├─ UID: {uid}\n"
                            f"├─ REGION: {data.get('region', 'Unknown')}\n"
                            f"└─ RESULT:\n"
                            f"   ├─ ADDED: +{data.get('likes_added', 0)}\n"
                            f"   ├─ BEFORE: {data.get('likes_before', 'N/A')}\n"
                            f"   └─ AFTER: {data.get('likes_after', 'N/A')}\n"
                            f"```"
                    )
                    else:
                        embed.description = (
                        f"\n"
                        f"``` MAX LIKES\n"
                        f"This UID has already received the maximum likes today. ```\n"
                        )

                    embed.set_footer(text="</>:  BRAYANZIN.CX44")
                    embed.description += "\n JOIN : https://discord.gg/VvJWxj6TrU"
                    await ctx.send(embed=embed, mention_author=True, ephemeral=is_slash)

        except asyncio.TimeoutError:
            await self._send_error_embed(ctx, "Timeout", "The server took too long to respond.", ephemeral=is_slash)
        except Exception as e:
            print(f"Unexpected error in like_command: {e}")
            await self._send_error_embed(ctx, "⚡ Critical Error", "An unexpected error occurred. Please try again later.", ephemeral=is_slash)

    async def _send_player_not_found(self, ctx, uid):
        embed = discord.Embed(title="❌ Player Not Found", description=f"The UID {uid} does not exist or is not accessible.", color=0xE74C3C)
        embed.add_field(name="Tip", value="Make sure that:\n- The UID is correct\n- The player is not private", inline=False)
        await ctx.send(embed=embed, ephemeral=True)
        
    async def _send_api_limit_reached(self, ctx):
        embed = discord.Embed(
            title="⚠️ API Rate Limit Reached",
            description="You have reached the maximum number of requests allowed by the API.",
            color=0xF1C40F  # jaune/orangé
        )
        embed.add_field(
            name="Tip",
            value=(
                "- Wait a few minutes before trying again\n"
                "- Consider upgrading your API plan if this happens often\n"
                "- Avoid sending too many requests in a short time"
            ),
            inline=False
        )
        await ctx.send(embed=embed, ephemeral=True)


    async def _send_api_error(self, ctx):
        embed = discord.Embed(title="⚠️ Service Unavailable", description="The Free Fire API is not responding at the moment.", color=0xF39C12)
        embed.add_field(name="Solution", value="Try again in a few minutes.", inline=False)
        await ctx.send(embed=embed, ephemeral=True)

    async def _send_error_embed(self, ctx, title, description, ephemeral=True):
        embed = discord.Embed(title=f"❌ {title}", description=description, color=discord.Color.red(), timestamp=datetime.now())
        embed.set_footer(text="An error occurred.")
        await ctx.send(embed=embed, ephemeral=ephemeral)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

async def setup(bot):
    await bot.add_cog(LikeCommands(bot))
