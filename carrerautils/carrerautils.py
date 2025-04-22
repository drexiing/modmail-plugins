from __future__ import annotations

import io
import json
import aiohttp
import discord

from discord.ext import commands
from urllib.parse import urlparse

from pathlib import Path
from typing import TYPE_CHECKING

from core.models import PermissionLevel
from core import checks

if TYPE_CHECKING:
    from bot import ModmailBot

info_json = Path(__file__).parent.resolve() / "info.json"
with open(info_json, encoding="utf-8") as f:
    __plugin_info__ = json.loads(f.read())

__plugin_name__ = __plugin_info__["name"]
__version__ = __plugin_info__["version"]
__description__ = "\n".join(__plugin_info__["description"]).format(__version__)

async def update_menu(menu, steps, current_step_index):
    lines = ["**Menú de creación de embed**"]
    for i, step in enumerate(steps):
        if i < current_step_index:
            lines.append(f"- ~~{step}~~")
        elif i == current_step_index:
            lines.append(f"- __{step}__")
        else:
            lines.append(f"- {step}")
    await menu.edit(content="\n".join(lines))

class CarreraUtils(commands.Cog, name=__plugin_name__):
    __doc__ = __description__
    
    def __init__(self, bot: ModmailBot):
        self.bot: ModmailBot = bot

    @commands.command()
    @commands.guild_only()
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    @commands.bot_has_permissions(send_messages=True, read_message_history=True, attach_files=True)
    async def say(self, ctx, channel_or_message: str = None, *, message: str = None):
        """
        Envía un mensaje como el bot.

        Este comando permite que el bot envíe un mensaje en un canal específico,
        o en el canal actual si no se indica uno.

        Es compatible con el envío de:
        - Mensajes de texto
        - Archivos adjuntos (imágenes, documentos, etc.)
        - Stickers (si la implementación lo permite)
        """
        if not (channel_or_message or message or ctx.message.attachments or ctx.message.stickers):
            return await ctx.reply(
                content=(
                    "Debes escribir un mensaje o subir un archivo para que el bot lo envíe. "
                    "También puedes mencionar un canal."
                )
            )

        arg_is_channel = False
        channel = ctx.channel
        files = []
        stickers = []

        if channel_or_message:
            if channel_or_message.startswith("<#") and channel_or_message.endswith(">"):
                if channel_or_message[2:-1].isdigit():
                    channel_id = int(channel_or_message[2:-1])
                    channel = ctx.bot.get_channel(channel_id)
                    if channel:
                        arg_is_channel = True
                    else:
                        channel = ctx.channel
            elif channel_or_message.isdigit():
                channel = ctx.bot.get_channel(int(channel_or_message))
                if channel: 
                    arg_is_channel = True
                else:
                    channel = ctx.channel

        if ctx.message.attachments:
            async with aiohttp.ClientSession() as session:        
                for attachment in ctx.message.attachments:
                    async with session.get(attachment.url) as response:
                        if response.status == 200:
                            file_data = await response.read()
                            files.append(discord.File(io.BytesIO(file_data), filename=attachment.filename))

        if ctx.message.stickers:
            stickers = ctx.message.stickers

        if arg_is_channel and message:
            content = message
        elif not arg_is_channel:
            content = f"{channel_or_message} {message}" if message else channel_or_message
        else:
            content = None

        if arg_is_channel and not (message or ctx.message.attachments or ctx.message.stickers):
            return await ctx.reply("Debes escribir un mensaje o subir un archivo para que el bot lo envíe.")
        
        try:
            await channel.send(
                content=content,
                files=files,
                stickers=stickers
            )
        except:
            await ctx.reply("Ha ocurrido un error al enviar el mensaje.")
        else:
            await ctx.message.delete()

    @commands.command()
    @commands.guild_only()
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    @commands.bot_has_permissions(send_messages=True, read_message_history=True)
    async def sync(self, ctx):
        """
        Sincroniza los comandos de aplicación (slash commands) del bot con la API de Discord.

        Este comando es útil cuando se han realizado cambios en el árbol de comandos,
        como añadir o eliminar comandos de aplicación.
        """
        try:
            await self.bot.tree.sync()
        except:
            await ctx.reply("Ha ocurrido un error al sincronizar los comandos de aplicación.")
        else:
            await ctx.reply("Comandos de aplicación sincronziados.")

    @commands.command()
    @commands.guild_only()
    @checks.has_permissions(PermissionLevel.ADMINISTRATOR)
    @commands.bot_has_permissions(send_messages=True, read_message_history=True, embed_links=True)
    async def embed(self, ctx, channel: discord.TextChannel = None):
        """
        Inicia un proceso interactivo para crear un embed.

        Este comando guía al usuario paso a paso para construir un mensaje embed,
        permitiendo personalizar los siguientes campos:
        - Autor (con icono opcional)
        - Título
        - Descripción
        - Color (se aceptan formatos hex, 0xhex y rgb)
        - Imagen
        - Miniatura (thumbnail)
        - Pie de página (footer, con icono opcional)

        Los pasos pueden saltarse escribiendo `skip`.

        Si no se especifica un canal, el embed se enviará en el canal actual.
        """
        colour = commands.ColourConverter
        if channel is None:
            channel = ctx.channel

        def check(message):
            return ctx.message and message.author == ctx.author and message.channel == ctx.channel
        
        steps = [
            "Autor del embed", "Título del embed", "Descripción del embed",
            "Color del embed", "Imagen del embed", "Miniatura del embed",
            "Footer del embed"
        ]
        embed_data = {}
        menu = await ctx.reply("**Menú de creación de embed**")

        try:
            for i, step in enumerate(steps):
                await update_menu(menu, steps, i)

                msg = await self.bot.wait_for("message", check=check, timeout=60.0)

                if step == "Autor del embed":
                    if msg.content != "skip":
                        embed_data["author_name"] = msg.content
                        if msg.attachments:
                            url = msg.attachments[0].url
                            if url.lower().endswith(("jpg", "jpeg", "png", "gif", "webp")):
                                embed_data["author_icon_url"] = url

                elif step == "Título del embed":
                    if msg.content != "skip":
                        embed_data["title"] = msg.content

                elif step == "Descripción del embed":
                    if msg.content != "skip":
                        embed_data["description"] = msg.content

                elif step == "Color del embed":
                    color = None
                    while color is None:
                        try:
                            color = await colour.convert(self, ctx, argument=msg.content)
                        except commands.BadArgument:
                            if msg.content == "skip":
                                color = int("34be22", 16)
                            else:
                                await ctx.reply("Color inválido. Intenta con `#hex`, `0xhex` o `rgb(...)`.")
                                msg = await self.bot.wait_for("message", check=check, timeout=60.0)
                    embed_data["color"] = color

                elif step == "Imagen del embed":
                    image_url = None
                    while image_url is None:
                        if msg.attachments:
                            parsed_url = urlparse(msg.attachments[0].url)
                            filename = parsed_url.path.split("/")[-1]
                            if filename.endswith(("jpg", "jpeg", "png", "gif", "webp")):
                                image_url = msg.attachments[0].url
                                break
                            else:
                                await ctx.reply("Por favor, indica la URL de una imagen o gif válidos.")
                                msg = await self.bot.wait_for("message", check=check, timeout=60.0)         
                        else:
                            if msg.content == "skip":
                                break
                            else:
                                await ctx.reply("Por favor, indica la URL de una imagen válida.")
                                msg = await self.bot.wait_for("message", check=check, timeout=60.0)
                    embed_data["image_url"] = image_url

                elif step == "Thumbnail del embed":
                    thumbnail_url = None
                    while thumbnail_url is None:
                        if msg.attachments:
                            parsed_url = urlparse(msg.attachments[0].url)
                            filename = parsed_url.path.split("/")[-1]
                            if filename.endswith(("jpg", "jpeg", "png", "gif", "webp")):
                                thumbnail_url = msg.attachments[0].url
                                break
                            else:
                                await ctx.reply("Por favor, indica la URL de una imagen o gif válidos.")
                                msg = await self.bot.wait_for("message", check=check, timeout=60.0)         
                        else:
                            if msg.content == "skip":
                                break
                            else:
                                await ctx.reply("Por favor, indica la URL de una imagen válida.")
                                msg = await self.bot.wait_for("message", check=check, timeout=60.0)
                    embed_data["thumbnail_url"] = thumbnail_url
                    
                elif step == "Footer del embed":
                    if msg.content != "skip":
                        embed_data["footer_text"] = msg.content
                        if msg.attachments:
                            url = msg.attachments[0].url
                            if url.lower().endswith(("jpg", "jpeg", "png", "gif", "webp")):
                                embed_data["footer_icon_url"] = url

            embed = discord.Embed(
                title=embed_data.get("title"),
                description=embed_data.get("description"),
                color=embed_data.get("color")
            )

            if "author_name" in embed_data:
                embed.set_author(
                    name=embed_data["author_name"],
                    icon_url=embed_data.get("author_icon_url")
                )

            if "image_url" in embed_data:
                embed.set_image(url=embed_data["image_url"])

            if "thumbnail_url" in embed_data:
                embed.set_image(url=embed_data["thumbnail_url"])

            if "footer_text" in embed_data:
                embed.set_footer(
                    name=embed_data["footer_text"],
                    icon_url=embed_data.get("footer_icon_url")
                )

            await ctx.send(embed=embed)
        except TimeoutError:    
            await menu.edit("**Menú de creación de embed expirado**")
                 
    @embed.error
    async def error(self, ctx, err):
        if isinstance(err, commands.CommandInvokeError):
            await ctx.reply("Formato inválido de embed, vuelve a intentarlo.")
         
async def setup(bot: ModmailBot)  -> None:
    await bot.add_cog(CarreraUtils(bot))