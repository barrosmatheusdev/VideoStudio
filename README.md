# 🎬 VideoStudio Local v2

**Legendagem automática + edição + estilização + queima de legenda 100% offline**

Uma ferramenta completa, leve e **totalmente local** para criar legendas profissionais usando Whisper + FFmpeg.

Perfeita para YouTubers, editores de vídeo, criadores de conteúdo e qualquer um que queira legendas bonitas sem depender de internet ou serviços pagos.

(![Demonstração do VideoStudio]https://i.imgur.com/ofRxUQP.gif)
> **GIF demonstrativo** — Veja o app em ação!

## ✨ Principais Recursos

- ✅ **Transcrição automática** com Whisper (modelo `small`)
- ✅ **Editor visual completo** com timeline interativa + waveform
- ✅ **Preview em tempo real** da legenda sobre o vídeo
- ✅ **Estilização avançada** (fonte, cor, contorno externo, caixa opaca, bold, itálico, posição)
- ✅ **Quebra automática** de legendas longas (máx. 5 palavras por linha)
- ✅ **Exportação com legenda queimada** (3 qualidades: Rápido / Bom / Máximo)
- ✅ **Interface moderna** em português
- ✅ **100% offline** — nada sai do seu PC
- ✅ Instalador automático para Windows

## 📥 Instalação (Windows)

1. Baixe o projeto
2. Certifique-se de ter **FFmpeg** instalado e adicionado ao PATH
3. Execute **`Instalador.bat`** (como administrador recomendado)
4. Aguarde a instalação do ambiente virtual e dependências
5. O programa abrirá automaticamente!

> Para abrir novamente depois, use o arquivo **`Abrir programa.bat`**

## 🚀 Como usar

1. Arraste ou selecione seu vídeo
2. Escolha o idioma e clique em **Transcrever**
3. Edite os tempos e textos na timeline ou na lista
4. Ajuste o estilo da legenda (posição, cor, contorno, etc.)
5. Clique em **Exportar vídeo** e escolha a qualidade

Pronto! O vídeo final sai com a legenda queimada.

## 🛠️ Tecnologias

- **Backend**: Flask + Whisper (OpenAI) + FFmpeg
- **Frontend**: HTML5 + Canvas + CSS moderno
- **Modelos**: PyTorch CPU + Whisper `small`
- **Instalação**: Ambiente virtual Python + scripts .bat

## 📌 Requisitos

- Windows 10/11
- Python 3.10 ou superior
- FFmpeg (obrigatório)
- Pelo menos 8 GB de RAM (recomendado)

## 📄 Licença

MIT License — sinta-se à vontade para usar, modificar e distribuir.

---

**Made with ❤️ for creators who value privacy and speed.**

Quer contribuir? Pull requests são bem-vindos!
