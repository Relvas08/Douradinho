import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
from collections import deque
import os  # Importa o módulo os para variáveis de ambiente

# --- Configurações ---
# ATENÇÃO: É ALTAMENTE RECOMENDADO NÃO DEIXAR O TOKEN DIRETO NO CÓDIGO!
# Para usar variáveis de ambiente:
# 1. Remova a linha 'TOKEN = ...' abaixo.
# 2. Defina uma variável de ambiente chamada 'DISCORD_BOT_TOKEN' (ou outro nome) com seu token.
#    Ex: No terminal, antes de rodar o bot: export DISCORD_BOT_TOKEN='SEU_TOKEN_AQUI' (Linux/macOS)
#    Ex: No terminal, antes de rodar o bot: set DISCORD_BOT_TOKEN=SEU_TOKEN_AQUI (Windows CMD)
#    Ex: Em plataformas como Replit, Heroku, etc., use a seção de "Secrets" ou "Environment Variables".
# <--- SUBSTITUA PELO SEU TOKEN REAL OU USE OS.GETENV
TOKEN = os.environ['BOT_TOKEN']
# Exemplo de uso seguro (remova a linha acima e descomente a linha abaixo):
# TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# O PREFIX é mantido se você ainda quiser que comandos de prefixo funcionem (ex: /play)
# Mas para slash commands, ele não é usado.
PREFIX = '/'

# Configurações do yt-dlp para extrair apenas o áudio
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'ytsearch',
    'quiet': True,
    'extract_flat': 'in_playlist',
    'outtmpl': '-',
    'logtostderr': False,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

# --- Inicialização do Bot ---
# Define os intents que seu bot usará.
# MESSAGE_CONTENT é necessário para ler o conteúdo das mensagens.
# MEMBERS é útil para gerenciar membros (pode ser útil para funcionalidades futuras).
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Inicializa o bot com o prefixo (para comandos de prefixo, se você os mantiver)
# e os intents.
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# --- Armazenamento Global da Fila ---
# Um dicionário para armazenar as filas por servidor (guild.id).
queues = {}

# --- Funções Auxiliares da Fila ---


async def play_next_song(interaction_or_ctx):
    """
    Inicia a reprodução da próxima música na fila do servidor.
    Adaptado para aceitar tanto Context (para comandos de prefixo) quanto Interaction (para slash commands).
    """
    # Determina o guild_id, voice_client e a função de envio de mensagem de forma flexível
    if isinstance(interaction_or_ctx, discord.Interaction):
        guild_id = interaction_or_ctx.guild.id
        voice_client = interaction_or_ctx.guild.voice_client
        # Para interações, a primeira resposta é via response.send_message
        # e as subsequentes via followup.send
        send_func = interaction_or_ctx.followup.send
    else:  # commands.Context (para comandos de prefixo, se você os usar)
        guild_id = interaction_or_ctx.guild.id
        voice_client = interaction_or_ctx.voice_client
        send_func = interaction_or_ctx.send

    if guild_id not in queues or not queues[guild_id]:
        if voice_client and voice_client.is_playing():
            voice_client.stop()
        await send_func("A fila de reprodução terminou.")
        return

    # Pega a próxima música do início da fila
    url, title, uploader = queues[guild_id].popleft()

    try:
        # Cria uma fonte de áudio a partir do URL usando FFmpeg
        audio_source = discord.FFmpegPCMAudio(
            url,
            before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
        )

        # Toca o áudio. O 'after' é CRUCIAL para chamar play_next_song novamente.
        voice_client.play(audio_source, after=lambda e: bot.loop.create_task(
            play_next_song(interaction_or_ctx)) if not e else print(f'Player error: {e}'))
        await send_func(f"Ei, escuta essa musiquinha comigo? **{title}** de **{uploader}**")

    except Exception as e:
        await send_func(f"Eu procurei, procurei, mas não achei. **{title}**. Erro: `{e}`. Bora pra próxima.")
        print(f"Erro ao tocar música: {e}")
        # Tenta tocar a próxima música mesmo se a atual falhar
        await play_next_song(interaction_or_ctx)


# --- Eventos do Bot ---

@bot.event
async def on_ready():
    """
    Evento disparado quando o bot se conecta com sucesso ao Discord.
    Aqui é onde registraremos os comandos de barra.
    """
    print(f'Bot {bot.user.name} está online!')
    print(f'ID: {bot.user.id}')
    print(f'Prefixo (para comandos de prefixo, se houver): {PREFIX}')

    # --- REGISTRO DOS COMANDOS DE BARRA (SLASH COMMANDS) ---
    try:
        # bot.tree.sync() registra os comandos de aplicação.
        #
        # Para REGISTRAR COMANDOS APENAS EM UM SERVIDOR ESPECÍFICO (ótimo para testes, mais rápido):
        # Descomente a linha abaixo e substitua 'SEU_GUILD_ID' pelo ID do seu servidor.
        # await bot.tree.sync(guild=discord.Object(id=SEU_GUILD_ID))
        #
        # Para REGISTRAR COMANDOS GLOBALMENTE (pode levar até 1 hora para aparecer em todos os servidores):
        await bot.tree.sync()
        print("Comandos de barra sincronizados com sucesso!")
    except Exception as e:
        print(f"Erro ao sincronizar comandos de barra: {e}")


@bot.event
async def on_command_error(ctx, error):
    """
    Lida com erros que ocorrem ao executar um comando de prefixo.
    (Comandos de barra têm seu próprio tratamento de erro em alguns casos ou falham silenciosamente se não tratados).
    """
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Comando não encontrado. Use `!help` para ver os comandos disponíveis.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Faltando argumento(s). Uso correto: `{PREFIX}{ctx.command.name} {ctx.command.signature}`")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("Você não tem permissão para usar este comando.")
    else:
        print(f"Erro no comando {ctx.command}: {error}")
        await ctx.send(f"Ocorreu um erro inesperado: {error}")

# --- Comandos do Bot (agora como Slash Commands) ---

# Cada comando de prefixo (@bot.command) foi transformado em um comando de barra (@bot.tree.command)
# e usa 'interaction: discord.Interaction' em vez de 'ctx'.


@bot.tree.command(name='join', description='Faz o bot entrar no seu canal de voz atual.')
async def join(interaction: discord.Interaction):
    """
    Comando para o bot entrar no canal de voz do autor da mensagem.
    """
    # Para comandos de barra, usamos interaction ao invés de ctx
    if not interaction.user.voice:
        # ephemeral=True faz com que a mensagem só seja visível para quem usou o comando
        await interaction.response.send_message(f"{interaction.user.name} não está conectado a um canal de voz.", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    # Usamos interaction.guild.voice_client para acessar o cliente de voz do guild
    if interaction.guild.voice_client:
        if interaction.guild.voice_client.channel == channel:
            await interaction.response.send_message("Já estou nesta disgraça!")
        else:
            await interaction.guild.voice_client.move_to(channel)
            await interaction.response.send_message(f"Movido para o canal: **{channel.name}**")
    else:
        await channel.connect()
        await interaction.response.send_message(f"Conectado ao canal: **{channel.name}**")


@bot.tree.command(name='leave', description='Faz o bot sair do canal de voz e limpa a fila.')
async def leave(interaction: discord.Interaction):
    """
    Comando para o bot sair do canal de voz e limpar a fila de reprodução.
    """
    if interaction.guild.voice_client:
        guild_id = interaction.guild.id
        if guild_id in queues:
            queues[guild_id].clear()
            del queues[guild_id]

        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Desconectado do canal de voz e fila limpa.")
    else:
        await interaction.response.send_message("Não estou conectado a um canal de voz.", ephemeral=True)


# Comando Play com Argumento de Slash Command
@bot.tree.command(name='play', description='Toca uma música do YouTube. Adiciona à fila se já estiver tocando.')
# Usamos app_commands.describe para adicionar a descrição do argumento
@app_commands.describe(query='Nome da música ou link do YouTube')
# Renomeei para 'query' para evitar conflito com 'search_query' interno
async def play(interaction: discord.Interaction, query: str):
    """
    Comando para tocar uma música ou adicionar à fila.
    Aceita nome da música ou link do YouTube.
    """
    if not interaction.guild.voice_client:
        await interaction.response.send_message("Não estou conectado a um canal de voz. Use `/join` primeiro.", ephemeral=True)
        return

    guild_id = interaction.guild.id
    if guild_id not in queues:
        queues[guild_id] = deque()

    # Primeira resposta ao slash command. Essencial para o Discord saber que o bot está processando.
    # O ephemeral=True faz com que a mensagem só seja visível para quem usou o comando.
    await interaction.response.send_message(f"Galelinha, péra: `{query}`...", ephemeral=True)

    try:
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            # `download=False` apenas extrai info, não baixa o arquivo completo
            info = ydl.extract_info(query, download=False)

            if 'entries' in info and info['entries']:
                video_info = info['entries'][0]
            else:
                video_info = info

            url = video_info['url']  # URL do stream de áudio
            title = video_info.get('title', 'Título Desconhecido')
            uploader = video_info.get('uploader', 'Desconhecido')

        # Adiciona a música (URL, título, uploader) à fila do servidor
        queues[guild_id].append((url, title, uploader))

        # Mensagens subsequentes à primeira resposta devem usar interaction.followup.send
        await interaction.followup.send(f"**{title}** de **{uploader}** adicionado à fila.")

        # Se o bot NÃO estiver tocando nada, inicia a reprodução da primeira música na fila.
        if not interaction.guild.voice_client.is_playing():
            # Passa a interação para a função auxiliar
            await play_next_song(interaction)

    except Exception as e:
        await interaction.followup.send(f"Não foi possível processar sua requisição para `{query}`. Erro: `{e}`")
        print(f"Erro ao adicionar música à fila: {e}")


@bot.tree.command(name='skip', description='Pula para a próxima música na fila.')
async def skip(interaction: discord.Interaction):
    """
    Comando para pular a música atual e ir para a próxima na fila.
    """
    if not interaction.guild.voice_client or not interaction.guild.voice_client.is_playing():
        await interaction.response.send_message("Nenhuma música está tocando para pular.", ephemeral=True)
        return

    guild_id = interaction.guild.id
    if guild_id not in queues or not queues[guild_id]:
        await interaction.response.send_message("Não há mais músicas na fila para pular.", ephemeral=True)
        return

    # Parar a música atual. Isso dispara o 'after' na função play_next_song.
    interaction.guild.voice_client.stop()
    await interaction.response.send_message("Música pulada.")


@bot.tree.command(name='queue', description='Mostra as músicas na fila.')
async def show_queue(interaction: discord.Interaction):
    """
    Comando para exibir a lista de músicas atualmente na fila.
    """
    guild_id = interaction.guild.id
    if guild_id not in queues or not queues[guild_id]:
        await interaction.response.send_message("A fila de reprodução está vazia.", ephemeral=True)
        return

    # Constrói uma mensagem incorporada (Embed) para exibir a fila de forma organizada
    embed = discord.Embed(title="Fila de Reprodução",
                          color=discord.Color.blue())

    # Adiciona cada música da fila como um campo no Embed
    for i, (_, title, uploader) in enumerate(queues[guild_id]):
        embed.add_field(name=f"{i+1}. {title}",
                        value=f"Por: {uploader}", inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='stop', description='Para a música que está tocando e limpa a fila.')
async def stop(interaction: discord.Interaction):
    """
    Comando para parar a música atual e limpar toda a fila de reprodução.
    """
    if interaction.guild.voice_client:
        if interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()

        guild_id = interaction.guild.id
        if guild_id in queues:
            queues[guild_id].clear()
            del queues[guild_id]

        await interaction.response.send_message("Música parada e fila limpa.")
    else:
        await interaction.response.send_message("Não há música tocando ou bot não está conectado.", ephemeral=True)

# --- Executa o Bot ---
bot.run(TOKEN)
