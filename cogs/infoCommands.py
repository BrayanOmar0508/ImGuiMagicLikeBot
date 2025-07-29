@commands.hybrid_command(name="info", description="Verifica una cuenta por UID o TAG")
@app_commands.describe(data="UID o TAG de la cuenta")
async def info(self, ctx: commands.Context, data: str):
    await ctx.defer()
    data = data.strip()
    try:
        id_data = await self.get_id(data)
        if not id_data:
            await ctx.reply("❌ No se pudo obtener el ID.", ephemeral=True)
            return

        uid, region = id_data.get("uid"), id_data.get("region")
        info = await self.get_player_data(uid, region)
        if not info:
            await ctx.reply("❌ No se pudo obtener la información del jugador.", ephemeral=True)
            return

        info_data = info.get("data", {})
        player = info_data.get("player", {})
        account = player.get("account", {})

        nickname = account.get("nickname", "Desconocido")
        level = player.get("level", 0)
        likes = player.get("likes", 0)
        created_at = account.get("createdAt", "Desconocido")
        country = account.get("country", "Desconocido")

        try:
            # Si la fecha es en formato timestamp
            if isinstance(created_at, (int, float)):
                created_at = datetime.utcfromtimestamp(created_at).strftime("%d/%m/%Y")
        except Exception:
            created_at = str(created_at)

        embed = discord.Embed(
            title=f"{nickname} ({region.upper()})",
            color=discord.Color.purple()
        )
        embed.add_field(name="🆔 UID", value=str(uid), inline=True)
        embed.add_field(name="📍 Región", value=region.upper(), inline=True)
        embed.add_field(name="🏅 Nivel", value=str(level), inline=True)
        embed.add_field(name="❤ Me gusta", value=str(likes), inline=True)
        embed.add_field(name="🌎 País", value=str(country), inline=True)
        embed.add_field(name="📅 Creado", value=str(created_at), inline=True)
        embed.set_footer(text="ImGui Magic", icon_url=ctx.bot.user.display_avatar.url)

        if region and uid:
            try:
                image_url = f"{self.generate_url}?uid={uid}"
                print(f"URL de la imagen = {image_url}")
                if image_url:
                    async with self.session.get(image_url) as img_file:
                        if img_file.status == 200:
                            with io.BytesIO(await img_file.read()) as buf:
                                file = discord.File(buf, filename=f"outfit_{uuid.uuid4().hex[:8]}.png")
                                
                                # ✅ Envía imagen y embed en un solo mensaje
                                await ctx.reply(embed=embed, file=file, mention_author=True)
                                print("Imagen y embed enviados juntos con éxito")
                        else:
                            print(f"Error HTTP al obtener la imagen: {img_file.status}")
            except Exception as e:
                print("La generación de la imagen falló:", e)
        else:
            # Si no hay imagen, manda solo el embed
            await ctx.reply(embed=embed, mention_author=True)

    except Exception as e:
        print("Error en el comando /info:", e)
        await ctx.reply("❌ Ocurrió un error procesando la solicitud.", ephemeral=True)
