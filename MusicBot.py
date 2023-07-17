import discord
import random
import asyncio
import yt_dlp
from discord.ext.commands import bot
from discord.ext import commands

TOKEN = ""
PREFIX = ''
GUILD = []  # Server ID to use
CHANNEL = []  # Channel ID for notifying entry and exit
bot = commands.Bot(command_prefix=PREFIX)
client = discord.Client()


@bot.event
async def on_voice_state_update(member, before, after):
    for i in range(len(GUILD)):
        if member.guild.id == GUILD[i] and (before.channel != after.channel):
            print(str(GUILD[i]) + ' ' + str(CHANNEL[i]))
            alert_channel = bot.get_channel(CHANNEL[i])
            if before.channel is None:
                msg = f'[Join] {member.name} が {after.channel.name} に参加しました。'
                await alert_channel.send(msg)
            elif after.channel is None:
                msg = f'[Leave] {member.name} が {before.channel.name} から退出しました。'
                await alert_channel.send(msg)


# ここから音楽--------------------------------------------------------------------------------------------------------------------
song_queue = []
tasker = None
yt_dlp.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

ffmpeg_options = {
    'before_options':
        '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
print(ytdl)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.25):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.duration = data.get('duration')
        self.url = ""

    @classmethod
    async def from_url(cls, url, *, loop=True, stream=False, play=False):
        loop = loop or asyncio.get_event_loop()
        yt = ytdl.extract_info(f"ytsearch:{url}", download=not stream or play)
        data = await loop.run_in_executor(None, lambda: yt)
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        fn = discord.FFmpegPCMAudio(filename, **ffmpeg_options)
        return cls(fn, data=data)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')


@bot.command(name='join', aliases=['c', 'j'], help='To make the bot connect the voice channel')
async def join(ctx):
    bot_voice = ctx.guild.voice_client
    author_voice = ctx.author.voice
    if (ctx.author.voice is None):  # 送信者がボイスチャンネルにいなければエラーを返す
        await ctx.send(f'{ctx.author.mention} ボイスチャンネルが見つかりません')
    elif author_voice and not bot_voice:  # botがボイスチャンネルに入っていなければ
        # 送信者の入っているボイスチャンネルのID
        voice_channel = ctx.author.voice.channel.id
        # ボイスチャンネルに入る
        await bot.get_channel(voice_channel).connect()


@bot.command(name='play', aliases=['p', 'play_song'], help='To play song')
async def play(ctx, *, url: str):
    global song_queue
    voice = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    print(url)
    try:
        if (voice == None):
            if not ctx.message.author.voice:
                await ctx.send(f"{ctx.message.author.name} is not connected to a voice channel")
            else:
                channel = ctx.message.author.voice.channel
                await channel.connect()
        async with ctx.typing():
            voice_client = ctx.message.guild.voice_client
            if not voice_client.is_playing():
                song_queue.clear()
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            if len(song_queue) == 0:
                await start_playing(ctx, player)
            else:
                song_queue.append(player)
                em = discord.Embed(description=f"**{player.title}** をプレイリストに追加しました ✅",
                                   color=random_color())
                await ctx.send(embed=em)
    except Exception as e:
        await ctx.send(f"Error occured: {e}")


@bot.command(name='leave', aliases=['l', 'exit'], help='To make the bot leave the voice channel')
async def leave(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_connected():
        await voice_client.disconnect()
    else:
        await ctx.send("The bot is not connected to a voice channel.")


async def start_playing(ctx, player):
    global song_queue
    song_queue.append(player)
    global tasker
    if (song_queue[0] == None):
        return
    i = 0
    while i < len(song_queue):
        try:
            ctx.voice_client.play(song_queue[0], after=lambda e: print('Player error: %s' % e) if e else None)
            em = discord.Embed(description=f"**{song_queue[0].title}** を再生します🎧", color=random_color())
            await ctx.send(embed=em)
        except Exception as e:
            await ctx.send(f"Something went wrong: {e}")
        await asyncio.sleep(song_queue[0].duration)
        tasker = asyncio.create_task(coro(ctx, song_queue[0].duration))
        try:
            await tasker
        except asyncio.CancelledError:
            print("Task cancelled")
        if (len(song_queue) > 0):
            song_queue.pop(0)


async def coro(ctx, duration):
    await asyncio.sleep(duration)


def random_color():
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    c = discord.Color.from_rgb(r, g, b)
    return c


@bot.command(name='queued', aliases=['q', 'list'], help='This command displays the queue')
async def queued(ctx):
    global song_queue
    a = ""
    i = 0
    for f in song_queue:
        if i > 0:
            a = a + str(i) + ". " + f.title + "\n "
        i += 1
    await ctx.send("Queued songs: \n " + a);


@bot.command(name='pause', help='This command pauses the song')
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        await ctx.send("Paused playing.")
        await voice_client.pause()
    else:
        await ctx.send("The bot is not playing anything at the moment.")


@bot.command(name='resume', help='Resumes the song')
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_paused():
        await ctx.send("Resumed playing.")
        await voice_client.resume()
    else:
        await ctx.send("The bot was not playing anything before this. Use play_song command")


@bot.command(name='stop', help='Stops the song')
async def stop(ctx):
    global tasker
    global song_queue
    voice_client = ctx.message.guild.voice_client
    try:
        if voice_client.is_playing():
            await ctx.send("Stopped playing.")
            song_queue.clear()
            voice_client.stop()
            tasker.cancel()
        else:
            await ctx.send("The bot is not playing anything at the moment.")
    except:
        await ctx.send("Type !play [URL/Title] to start music!")


@bot.command(name='skip', help='Skip the song')
async def skip(ctx):
    global tasker
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.stop()
        tasker.cancel()
        await ctx.send("Skipped song.")
    else:
        await ctx.send("The bot is not playing anything at the moment.")


bot.run(TOKEN)
