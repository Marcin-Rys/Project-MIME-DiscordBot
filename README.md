This is a **ONLY** part of an Project-MIME, for installation, please refer to:

### [GO TO INSTALLATION REPOSITORY](https://github.com/Marcin-Rys/Project-MIME-Installer)

*FYI: This repository is for DiscordBot engine only, uses an discord.py API, there is also an [WebApp](https://github.com/Marcin-Rys/Project-MIME-WebApp) which is an WebGUI using database created by this engine.*

## Quick Start with Docker

1. Copy example files and fill in your values:
   ```bash
   cp .env.example .env
   cp config/config.json.example config/config.json
   cp config/modules.json.example config/modules.json
   cp data/ama.json.example data/ama.json
   cp data/swears.json.example data/swears.json
   cp data/statuses.json.example data/statuses.json
   ```

2. Edit `.env` and set your `DISCORD_TOKEN`.

3. Build and run with Docker Compose:
   ```bash
   docker compose up -d
   ```

4. To sync slash commands with Discord (once the bot is running), use the `!sync` prefix command or the `/sync` slash command as the bot owner.

## License
This project is licensed under the **GNU Affero General Public License v3.0**. See the [LICENSE](LICENSE) file for details.

## Acknowledgements
This bot uses sound assets from the [tgstation/tgstation](https://github.com/tgstation/tgstation) project, which are also licensed under the AGPL-3.0.
