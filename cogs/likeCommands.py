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
        self.api_host = "https://freelike-nx2.vercel.app/"
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
                print(f"ADVERTENCIA: El archivo de configuración '{CONFIG_FILE}' está corrupto o vacío. Restableciendo la configuración por defecto.")
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

    @commands.hybrid_command(name="setlikechannel", description="✅ Permitir el comando /like en un canal.", with_app_command=True)
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="El canal en el que se permitirá el comando /like.")
    async def set_like_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        server_config = self.config_data["servers"].setdefault(guild_id, {})
        like_channels = server_config.setdefault("like_channels", [])

        channel_id_str = str(channel.id)

        if channel_id_str in like_channels:
            await ctx.send(f"⚠️ {channel.mention} ya está permitido para /like.", ephemeral=True)
        else:
            like_channels.append(channel_id_str)
            self.save_config()
            await ctx.send(f"✅ {channel.mention} ha sido añadido a los canales permitidos para /like.", ephemeral=True)

    @commands.hybrid_command(name="removelikechannel", description="❌ No permitir el comando /like en un canal.", with_app_command=True)
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="El canal en el que no se permitirá el comando /like.")
    async def remove_like_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        server_config = self.config_data["servers"].setdefault(guild_id, {})
        like_channels = server_config.setdefault("like_channels", [])

        channel_id_str = str(channel.id)

        if channel_id_str in like_channels:
            like_channels.remove(channel_id_str)
            self.save_config()
            await ctx.send(f"❌ {channel.mention} ha sido eliminado de los canales permitidos para /like.", ephemeral=True)
        else:
            await ctx.send(f"⚠️ {channel.mention} no estaba en la lista de canales permitidos.", ephemeral=True)

    @commands.hybrid_command(name="likechannels", description="📜 Listar los canales permitidos para el comando /like.", with_app_command=True)
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def list_like_channels(self, ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        server_config = self.config_data["servers"].get(guild_id, {})
        like_channels = server_config.get("like_channels", [])

        if not like_channels:
            await ctx.send("ℹ️ No hay canales restringidos — `/like` está permitido en todas partes.", ephemeral=True)
            return

        mentions = []
        for channel_id in like_channels:
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                mentions.append(channel.mention)
            else:
                mentions.append(f"<#{channel_id}>")

        channels_list = "\n".join(mentions)
        await ctx.send(f"✅ `/like` está permitido en los siguientes canales:\n{channels_list}", ephemeral=True)

    @commands.hybrid_command(name="like", description="Envía likes a un jugador de Free Fire")
    @app_commands.describe(uid="UID del jugador (solo números, mínimo 6 caracteres)")
    async def like_command(self, ctx: commands.Context, uid: str):
        is_slash = ctx.interaction is not None

        if not await self.check_channel(ctx):
            guild_id = str(ctx.guild.id)
            allowed_ids = self.config_data["servers"].get(guild_id, {}).get("like_channels", [])

            if allowed_ids:
                allowed_mentions = ", ".join(f"<#{ch_id}>" for ch_id in allowed_ids)
                msg = (
                    f"🚫 Este comando **no está permitido** en este canal.\n"
                    f"✅ Puedes usarlo en: {allowed_mentions}"
                )
            else:
                msg = "🚫 Este comando **no está permitido** en este canal y no hay canales permitidos configurados."
            
            await ctx.send(msg, ephemeral=True)
            return

        user_id = ctx.author.id
        cooldown = 30
        if user_id in self.cooldowns:
            last_used = self.cooldowns[user_id]
            remaining = cooldown - (datetime.now() - last_used).seconds
            if remaining > 0:
                await ctx.send(f"Por favor, espera {remaining} segundos antes de usar este comando de nuevo.", ephemeral=True)
                return
        self.cooldowns[user_id] = datetime.now()

        if not uid.isdigit() or len(uid) < 6:
            await ctx.send("UID inválido. Debe contener solo números y tener al menos 6 caracteres.", ephemeral=True)
            return

        try:
            await ctx.defer(ephemeral=False)
            async with self.session.get(f"{self.api_host}/like?uid={uid}", headers=self.headers) as response:
                if response.status == 404:
                    await self._send_player_not_found(ctx, uid)
                    return
                if response.status != 200:
                    print(f"Error de API: {response.status} - {await response.text()}")
                    await self._send_api_error(ctx)
                    return

                data = await response.json()
                embed = discord.Embed(
                    title="LIKES PARA FREE FIRE",
                    color=0x2ECC71 if data.get("status") == 1 else 0xE74C3C,
                    timestamp=datetime.now()
                )

                if data.get("status") == 1:
                    embed.description = (
                        f"```\n"
                        f"┌  CUENTA\n"
                        f"├─ APODO: {data.get('nickname', 'Desconocido')}\n"
                        f"├─ UID: {uid}\n"
                        f"├─ REGIÓN: {data.get('region', 'Desconocida')}\n"
                        f"└─ RESULTADO:\n"
                        f"    ├─ AÑADIDOS: +{data.get('likes_added', 0)}\n"
                        f"    ├─ ANTES: {data.get('likes_before', 'N/A')}\n"
                        f"    └─ DESPUÉS: {data.get('likes_after', 'N/A')}\n"
                        f"```"
                    )
                else:
                    embed.description = (
                        f"\n"
                        f"```LIKES MÁXIMOS\n"
                        f"Este UID ya ha recibido el máximo de likes por hoy.```\n"
                    )

                embed.set_footer(text="</>:  BRAYANZIN.CX44")
                embed.description += "\nÚNETE: https://discord.gg/VvJWxj6TrU"
                await ctx.send(embed=embed)

        except asyncio.TimeoutError:
            await self._send_error_embed(ctx, "Tiempo de espera agotado", "El servidor tardó demasiado en responder.", ephemeral=True)
        except Exception as e:
            print(f"Error inesperado en like_command: {e}")
            await self._send_error_embed(ctx, "⚡ Error Crítico", "Ocurrió un error inesperado. Por favor, inténtalo de nuevo más tarde.", ephemeral=True)

    async def _send_player_not_found(self, ctx, uid):
        embed = discord.Embed(title="❌ Jugador No Encontrado", description=f"El UID {uid} no existe o no es accesible.", color=0xE74C3C)
        embed.add_field(name="Consejo", value="Asegúrate de que:\n- El UID es correcto\n- El perfil del jugador no es privado", inline=False)
        await ctx.send(embed=embed, ephemeral=True)
        
    async def _send_api_limit_reached(self, ctx):
        embed = discord.Embed(
            title="⚠️ Límite de Tasa de API Alcanzado",
            description="Has alcanzado el número máximo de solicitudes permitidas por la API.",
            color=0xF1C40F
        )
        embed.add_field(
            name="Consejo",
            value=(
                "- Espera unos minutos antes de volver a intentarlo\n"
                "- Considera mejorar tu plan de API si esto ocurre a menudo\n"
                "- Evita enviar demasiadas solicitudes en poco tiempo"
            ),
            inline=False
        )
        await ctx.send(embed=embed, ephemeral=True)

    async def _send_api_error(self, ctx):
        embed = discord.Embed(title="⚠️ Servicio No Disponible", description="La API de Free Fire no está respondiendo en este momento.", color=0xF39C12)
        embed.add_field(name="Solución", value="Inténtalo de nuevo en unos minutos.", inline=False)
        await ctx.send(embed=embed, ephemeral=True)

    async def _send_error_embed(self, ctx, title, description, ephemeral=True):
        embed = discord.Embed(title=f"❌ {title}", description=description, color=discord.Color.red(), timestamp=datetime.now())
        embed.set_footer(text="Ocurrió un error.")
        await ctx.send(embed=embed, ephemeral=ephemeral)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

async def setup(bot):
    await bot.add_cog(LikeCommands(bot))
