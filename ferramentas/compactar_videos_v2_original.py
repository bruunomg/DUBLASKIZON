import os
import subprocess
import glob
import sys
import time

# --- Configurações ---
# Pasta de saída para os vídeos compactados
OUTPUT_DIR = "videos compacto H265"
# Extensões de arquivo de vídeo a serem processadas
VIDEO_EXTENSIONS = ["mp4", "mkv", "avi", "mov"]
# Comando base do FFmpeg (use %s para o arquivo de entrada e %s para o arquivo de saída)
# O comando agora usa -y para sobrescrever sem perguntar e -hide_banner para limpar a saída
FFMPEG_COMMAND_TEMPLATE = (
    'ffmpeg -y -hide_banner -i "%s" -c:v libx265 -crf 28 -preset medium -c:a aac -b:a 128k "%s"'
)
# ---------------------

def format_bytes(size):
    """Formata o tamanho do arquivo em uma string legível (ex: 1.2 GB)"""
    power = 2**10
    n = 0
    power_labels = {0 : 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"

def processar_video(input_file, output_file):
    """Executa o FFmpeg e exibe o progresso em tempo real."""
    
    # Monta o comando FFmpeg
    command = FFMPEG_COMMAND_TEMPLATE % (input_file, output_file)
    
    print(f"Comando a ser executado: {command}")
    
    # Usa subprocess.Popen para obter feedback em tempo real
    # stderr é usado porque o FFmpeg envia o progresso para lá
    process = subprocess.Popen(
        command, 
        shell=True, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        text=True,
        encoding='utf-8'
    )

    # Exibe o progresso em tempo real
    print("\n--- Progresso do FFmpeg (em tempo real) ---")
    
    # Lê a saída de erro (onde o FFmpeg envia o progresso) linha por linha
    for line in process.stderr:
        # Filtra as linhas de progresso e as imprime
        if "frame=" in line or "size=" in line or "time=" in line:
            # Imprime a linha de progresso, sobrescrevendo a anterior
            sys.stdout.write(f"\r{line.strip()}")
            sys.stdout.flush()
        # Imprime outras mensagens importantes
        elif "error" in line.lower() or "warning" in line.lower():
            print(f"\n[AVISO/ERRO FFmpeg] {line.strip()}")
    
    # Espera o processo terminar e obtém o código de retorno
    process.wait()
    
    print("\n--- Fim do Progresso do FFmpeg ---\n")
    
    return process.returncode

def compactar_videos():
    """
    Procura por arquivos de vídeo na pasta atual e os compacta usando FFmpeg
    para H.265, salvando-os na pasta de saída.
    """
    print("=" * 60)
    print("Iniciando a compactação de vídeos para H.265 (HEVC) com FFmpeg")
    print("=" * 60)

    # 1. Cria a pasta de saída se ela não existir
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"[INFO] Pasta de saída '{OUTPUT_DIR}' criada.")

    # 2. Encontra todos os arquivos de vídeo na pasta atual
    video_files = []
    for ext in VIDEO_EXTENSIONS:
        video_files.extend(glob.glob(f"*.{ext}"))

    if not video_files:
        print("[INFO] Nenhum arquivo de vídeo encontrado na pasta atual.")
        return

    # 3. Processa cada arquivo de vídeo
    for input_file in video_files:
        output_file = os.path.join(OUTPUT_DIR, input_file)

        print("\n" + "=" * 60)
        print(f"[PROCESSANDO] Arquivo: '{input_file}'")
        
        # Verifica se o arquivo de saída já existe
        if os.path.exists(output_file):
            print(f"[PULAR] Arquivo de saída já existe: '{output_file}'.")
            continue

        # Obtém o tamanho do arquivo original
        try:
            original_size = os.path.getsize(input_file)
            print(f"[INFO] Tamanho Original: {format_bytes(original_size)}")
        except FileNotFoundError:
            print(f"[ERRO] Arquivo de entrada não encontrado: {input_file}")
            continue

        # Executa o FFmpeg
        return_code = processar_video(input_file, output_file)

        # 4. Verifica o resultado e fornece feedback detalhado
        if return_code == 0:
            try:
                compressed_size = os.path.getsize(output_file)
                reduction = 100 - (compressed_size / original_size * 100)
                
                print("=" * 60)
                print(f"[SUCESSO] Compactação de '{input_file}' concluída.")
                print(f"  -> Tamanho Compactado: {format_bytes(compressed_size)}")
                print(f"  -> Redução de Tamanho: {reduction:.2f}%")
                print("=" * 60)
            except FileNotFoundError:
                print(f"[ERRO] O FFmpeg terminou, mas o arquivo de saída não foi encontrado: {output_file}")
        else:
            print("=" * 60)
            print(f"[FALHA] O FFmpeg retornou um erro (Código: {return_code}).")
            print("Verifique se o FFmpeg está instalado corretamente e se o arquivo de entrada não está corrompido.")
            print("=" * 60)

    print("\n" + "#" * 60)
    print("### TODOS OS VÍDEOS FORAM PROCESSADOS. COMPACTAÇÃO CONCLUÍDA. ###")
    print("#" * 60)

if __name__ == "__main__":
    compactar_videos()
