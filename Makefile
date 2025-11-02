# Makefile para Bot de Trading en Vivo
.PHONY: help build run stop logs shell clean test

# Variables
IMAGE_NAME = auto-trader-bot
CONTAINER_NAME = auto-trader-bot
CONFIG_FILE = conf.yaml

help: ## Muestra esta ayuda
	@echo "🤖 Bot de Trading en Vivo - Comandos disponibles:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""

build: ## Construir la imagen Docker
	@echo "🔨 Construyendo imagen Docker..."
	docker build -t $(IMAGE_NAME):latest .
	@echo "✅ Imagen construida: $(IMAGE_NAME):latest"

run: ## Ejecutar el bot en contenedor
	@echo "🚀 Iniciando bot en contenedor..."
	@if [ -f .env ]; then \
		export $(cat .env | grep -v '^#' | xargs); \
	fi
	@if [ ! -f $(CONFIG_FILE) ] && [ -z "$$BITGET_API_KEY" ]; then \
		echo "❌ Error: $(CONFIG_FILE) no encontrado y variables de entorno no configuradas"; \
		echo "   Ejecuta: make setup  (para crear conf.yaml)"; \
		echo "   O crea archivo .env con tus credenciales"; \
		exit 1; \
	fi
	@if [ -f .env ]; then \
		docker run -d \
			--name $(CONTAINER_NAME) \
			--restart unless-stopped \
			-v $(PWD)/logs:/app/logs \
			--env-file .env \
			$(IMAGE_NAME):latest; \
	else \
		docker run -d \
			--name $(CONTAINER_NAME) \
			--restart unless-stopped \
			-v $(PWD)/$(CONFIG_FILE):/app/conf.yaml:ro \
			-v $(PWD)/logs:/app/logs \
			-e BITGET_API_KEY="$(BITGET_API_KEY)" \
			-e BITGET_API_SECRET="$(BITGET_API_SECRET)" \
			-e BITGET_API_PASSPHRASE="$(BITGET_API_PASSPHRASE)" \
			-e BITGET_SANDBOX="$(BITGET_API_PASSPHRASE)" \
			$(IMAGE_NAME):latest; \
	fi
	@echo "✅ Bot iniciado. Usa 'make logs' para ver los logs."

stop: ## Detener el bot
	@echo "🛑 Deteniendo bot..."
	docker stop $(CONTAINER_NAME) || true
	docker rm $(CONTAINER_NAME) || true
	@echo "✅ Bot detenido"

restart: stop run ## Reiniciar el bot

logs: ## Ver logs del bot en tiempo real
	@echo "📊 Logs del bot (Ctrl+C para salir)..."
	docker logs -f $(CONTAINER_NAME)

logs-file: ## Ver logs desde el archivo
	@tail -f logs/bot_log.jsonl || echo "No hay logs aún"

status: ## Ver estado del contenedor
	@docker ps -a --filter name=$(CONTAINER_NAME) --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

shell: ## Abrir shell en el contenedor
	docker exec -it $(CONTAINER_NAME) /bin/bash

test-connection: ## Probar conexión a Bitget (sin ejecutar bot)
	@echo "🔍 Probando conexión a Bitget..."
	docker run --rm \
		-v $(PWD)/$(CONFIG_FILE):/app/conf.yaml:ro \
		-e BITGET_API_KEY="$(BITGET_API_KEY)" \
		-e BITGET_API_SECRET="$(BITGET_API_SECRET)" \
		-e BITGET_API_PASSPHRASE="$(BITGET_API_PASSPHRASE)" \
		$(IMAGE_NAME):latest \
		python -c "from bot.bitget_client import BitgetClient; import yaml; config = yaml.safe_load(open('/app/conf.yaml')); client = BitgetClient(config['BITGET_API_KEY'], config['BITGET_API_SECRET'], config['BITGET_API_PASSPHRASE'], config.get('BITGET_SANDBOX', False)); print('✅ Conexión exitosa'"

setup: ## Crear archivo de configuración desde plantilla
	@if [ ! -f $(CONFIG_FILE) ]; then \
		cp conf.yaml.example $(CONFIG_FILE); \
		echo "✅ Archivo $(CONFIG_FILE) creado desde plantilla"; \
		echo "   Edita $(CONFIG_FILE) con tus credenciales antes de ejecutar"; \
	else \
		echo "⚠️  $(CONFIG_FILE) ya existe"; \
	fi

clean: ## Limpiar contenedores e imágenes
	@echo "🧹 Limpiando..."
	docker stop $(CONTAINER_NAME) 2>/dev/null || true
	docker rm $(CONTAINER_NAME) 2>/dev/null || true
	docker rmi $(IMAGE_NAME):latest 2>/dev/null || true
	@echo "✅ Limpieza completada"

clean-logs: ## Limpiar archivos de log
	@rm -f logs/*.jsonl
	@echo "✅ Logs eliminados"

update: ## Reconstruir imagen y reiniciar bot
	@echo "🔄 Actualizando bot..."
	$(MAKE) build
	$(MAKE) restart
	@echo "✅ Bot actualizado y reiniciado"

# Comando para ejecutar en servidor de producción
run-prod: ## Ejecutar en modo producción (con restart automático)
	@echo "🚀 Iniciando bot en modo PRODUCCIÓN..."
	@if [ -f .env ]; then \
		export $(cat .env | grep -v '^#' | xargs); \
	fi
	@if [ -z "$$BITGET_API_KEY" ] || [ -z "$$BITGET_API_SECRET" ] || [ -z "$$BITGET_API_PASSPHRASE" ]; then \
		echo "❌ Error: Variables de entorno no configuradas"; \
		echo "   Crea archivo .env o exporta: BITGET_API_KEY, BITGET_API_SECRET, BITGET_API_PASSPHRASE"; \
		exit 1; \
	fi
	@if [ -f .env ]; then \
		docker run -d \
			--name $(CONTAINER_NAME) \
			--restart always \
			-v $(PWD)/logs:/app/logs \
			--env-file .env \
			-e BITGET_SANDBOX=false \
			$(IMAGE_NAME):latest; \
	else \
		docker run -d \
			--name $(CONTAINER_NAME) \
			--restart always \
			-v $(PWD)/logs:/app/logs \
			-e BITGET_API_KEY="$$BITGET_API_KEY" \
			-e BITGET_API_SECRET="$$BITGET_API_SECRET" \
			-e BITGET_API_PASSPHRASE="$$BITGET_API_PASSPHRASE" \
			-e BITGET_SANDBOX=false \
			-e SYMBOL=BTC/USDT:USDT \
			-e LEVERAGE=25 \
			$(IMAGE_NAME):latest; \
	fi
	@echo "✅ Bot en producción iniciado"

