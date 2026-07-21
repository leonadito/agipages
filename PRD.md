# PRD — Sistema de Landing Pages para Lançamentos Imobiliários

**Status:** Rascunho para validação
**Autor:** Leonardo Duarte
**Data:** 2026-07-21

---

## 1. Visão geral

Um SaaS multi-tenant onde corretores/imobiliárias criam landing pages de captura de leads para lançamentos imobiliários (ex: casas em Tramandaí, Diamond Infinity Towers) preenchendo um formulário estruturado — sem precisar de designer ou desenvolvedor — e depois administram os leads recebidos em um painel próprio, com notificação em tempo real via Telegram.

Referência de layout: `landing-page-exemplo.png` (ver seção 4 — Anatomia da landing page).
Referência de conteúdo real: pasta `diamond-infinity-towers/` (imagens do empreendimento, condições de pagamento, criativos de anúncio, folder em PDF).

## 2. Problema

Imobiliárias e corretores hoje dependem de terceiros (agências, freelancers) para publicar uma landing page por lançamento, o que é lento e caro. Cada lançamento precisa de uma página nova, rápida de montar, com captura de lead e visibilidade de quem preencheu o formulário — hoje isso costuma ficar espalhado em planilhas, e-mail ou grupos de WhatsApp sem centralização.

## 3. Objetivo e métricas de sucesso

- Um usuário consegue publicar uma landing page nova em menos de 15 minutos, sem código.
- 100% dos leads capturados aparecem no painel em tempo real, sem perda.
- Notificação do lead chega no Telegram em até alguns segundos após o envio do formulário.
- Taxa de erro de publicação (domínio/SSL) próxima de zero após o fluxo de verificação.

## 4. Escopo

### 4.1 Dentro do MVP
- Cadastro/login multi-tenant (cada conta só vê suas próprias páginas e leads).
- Criação de landing page via **formulário estruturado**, com template único focado em imóveis (seção 5).
- Publicação com **domínio próprio** (custom domain) por landing page.
- Página pública responsiva (mobile-first) construída em Django + HTMX + Alpine.js + Tailwind CSS.
- Captura de lead via formulário (submissão HTMX, sem reload de página).
- Captura de parâmetros UTM e IDs de rastreamento (Facebook Pixel, Google Ads) por página.
- Painel de gestão de leads: listagem, filtro, pipeline de status, exportação CSV.
- Notificação de novo lead em tempo real via **Telegram** (bot).

### 4.2 Fora de escopo (fases futuras)
- Billing/planos pagos e limites de uso.
- Conformidade LGPD completa (checkbox de consentimento, política de privacidade, exclusão de dados a pedido) — **registrado como dívida/risco a resolver antes de ir para produção com dados reais de terceiros**, ver seção 9.
- Builder de blocos/seções arrastáveis (drag-and-drop) — o MVP usa template único de imóveis.
- Múltiplos templates por vertical (evento, produto, serviço).
- Integração com CRM externo, WhatsApp API, e-mail marketing.

## 5. Anatomia da landing page (template de imóveis)

Baseado no exemplo (`landing-page-exemplo.png`) e no conteúdo real (`diamond-infinity-towers/`), o template estruturado tem estas seções, cada uma editável no formulário de criação:

| # | Seção | Campos |
|---|---|---|
| 1 | Hero | Imagem/vídeo de fundo, título (H1), subtítulo, texto e link do botão CTA |
| 2 | Faixa de destaque | Texto curto de reforço (fundo escuro) |
| 3 | Galeria/carrossel | Upload de múltiplas imagens (ordenável), autoplay opcional |
| 4 | Condições financeiras | Valor de entrada, valor de parcela, valor total, texto de financiamento |
| 5 | Formulário de captura | Campos configuráveis (nome, e-mail, telefone, cidade são o padrão), texto de cabeçalho/descrição, cor/texto do botão |
| 6 | Vídeo institucional | URL de vídeo (YouTube/Vimeo embed) com título da seção |
| 7 | Requisitos | Título + texto rico (lista de condições, ex: "sem restrição SPC/Serasa") |
| 8 | Características do imóvel | Título + texto rico + imagem lateral |
| 9 | Seção de orçamento/oportunidade | Texto rico de reforço de conversão |
| 10 | CTA final + rodapé | Botão repetido do CTA principal + nome do empreendimento/rodapé |

O formulário de captura (seção 5) aparece quantas vezes o usuário quiser reaproveitar (hero CTA e CTA final apontam para a mesma seção, como no exemplo).

## 6. Personas

- **Corretor/imobiliária (usuário do SaaS):** cria a página, divulga o link/domínio em anúncios, acompanha e trabalha os leads recebidos.
- **Lead (visitante):** acessa o anúncio, entra na landing page, preenche o formulário.
- **(Futuro) Admin da plataforma:** operação interna do SaaS, sem tela definida neste PRD.

## 7. Requisitos funcionais detalhados

### 7.1 Contas e multi-tenancy
- Cada conta (tenant) tem usuário(s), landing pages e leads isolados — um tenant nunca vê dados de outro.
- Login/cadastro simples (e-mail + senha). Papéis de usuário (admin da conta vs. membro) podem ficar como stretch goal, não bloqueante para o MVP.

### 7.2 Criação e edição de landing page
- Formulário multi-etapas (ou single-page com Alpine.js) cobrindo as 10 seções da tabela acima.
- Upload de imagens com preview antes de salvar.
- Rascunho vs. Publicado — página só fica acessível publicamente depois de publicada (ver estrutura de URL na seção 7.3).

### 7.3 Estrutura de URL e domínio próprio

O domínio próprio é configurado **por tenant (conta), não por landing page**, em um fluxo separado ("Configurações da conta > Domínio") — criar e publicar uma landing page nunca depende de ter um domínio configurado.

- **Sem domínio próprio configurado (padrão):** cada landing page publicada fica disponível em `meusaas.com/<slug-do-tenant>/<slug-da-página>`.
- **Com domínio próprio configurado e verificado:** as landing pages do tenant passam a ficar disponíveis em `<domínio-do-tenant>/<slug-da-página>` (ex: `diamondtowers.com.br/landing-page-1`). Novas landing pages criadas depois já nascem disponíveis nesse domínio, sem precisar de nova verificação de DNS.
- Fluxo de configuração de domínio (independente da criação de páginas): usuário informa o domínio desejado → sistema mostra instruções de DNS (registro CNAME ou A, a definir na fase técnica) → botão "verificar domínio" → emissão automática de certificado SSL após verificação (via proxy reverso, ex: Traefik com ACME — ver seção 10).
- Roteamento: o Django precisa resolver o tenant a partir do `Host` header (quando é domínio próprio) **ou** do primeiro segmento do path (quando é o fallback `meusaas.com/<slug-do-tenant>/...`) — um único middleware de resolução de tenant cobre os dois casos.
- **Importante (isolamento):** esse slug de tenant na URL serve só de roteamento para a página pública (que é intencionalmente pública). O painel administrativo de leads nunca deve inferir o tenant a partir de um segmento de URL — o tenant do painel vem sempre da sessão do usuário autenticado, e toda query de lead/landing page filtra por esse tenant, independente do que estiver na URL.
- Rascunho vs. Publicado — página só fica acessível publicamente (por qualquer uma das duas formas de URL) depois de publicada.
- Slug da landing page gerado automaticamente a partir do título, editável antes de publicar.

### 7.4 Página pública
- Renderização server-side (Django templates), com HTMX para:
  - Envio do formulário de lead sem reload.
  - Navegação do carrossel de imagens.
- Alpine.js para interações client-side leves (abrir/fechar, estado do carrossel, validação inline).
- Responsiva mobile-first (tráfego majoritariamente de anúncios em redes sociais).
- Captura automática de parâmetros de URL (`utm_source`, `utm_medium`, `utm_campaign`, etc.) — independe de domínio próprio ou path, é apenas query string do request.
- Injeção de Facebook Pixel / Google Ads: IDs configurados **por landing page** (não por tenant/domínio), já que um mesmo cliente pode rodar campanhas diferentes — com pixels/eventos de conversão diferentes — em landing pages distintas dentro do mesmo domínio.

### 7.5 Captura de leads
- Submissão do formulário cria um `Lead` vinculado à landing page e ao tenant.
- Lead armazena: dados do formulário, timestamp, UTM capturados, IP/user-agent (para fins de auditoria/anti-spam básico).
- Confirmação visual ao usuário (mensagem de sucesso via HTMX swap), sem redirecionar para outra página.
- Proteção anti-spam básica no MVP (honeypot field e/ou rate limit por IP) — sem captcha completo por padrão.

### 7.6 Painel de gestão de leads
- Listagem de leads por landing page e visão consolidada de todas as páginas do tenant.
- Filtros por período, landing page, status, origem (UTM).
- Pipeline/status do lead: Novo → Contatado → Qualificado → Convertido → Perdido (customização de nomes fica como stretch goal).
- Alteração de status inline, com histórico de mudanças (quem mudou e quando).
- Exportação da lista filtrada em CSV/Excel.

### 7.7 Notificação em tempo real (Telegram)
- Usuário conecta uma conta/chat do Telegram à sua conta no sistema (via bot próprio da plataforma, fluxo tipo "envie /start para o bot e cole o código aqui" para vincular o `chat_id`).
- Ao chegar um novo lead, o sistema envia mensagem ao Telegram do usuário com: nome da landing page, dados do lead, link direto para o lead no painel.
- Envio síncrono, com timeout curto (1-2s) e falha silenciosa (`try/except`): o lead já foi salvo antes da chamada ao Telegram, então uma falha na notificação nunca deve impedir a resposta de sucesso ao visitante. Sem fila/broker no MVP — reavaliar (Celery/RQ) apenas se o volume de leads justificar.

## 8. Requisitos não funcionais

- **Performance:** página pública deve carregar rápido em conexão móvel (otimização de imagens, lazy loading na galeria).
- **Segurança/isolamento:** garantir que queries de lead e landing page sempre filtrem por tenant (nunca por ID solto) para evitar vazamento entre contas. O slug de tenant que aparece na URL pública (`meusaas.com/<slug>/...`) é só roteamento de página pública — o painel administrativo nunca deve usar esse segmento de URL para decidir de qual tenant exibir dados; o tenant do painel vem sempre da sessão do usuário autenticado.
- **Disponibilidade da página pública:** é a página que recebe tráfego pago (anúncios) — indisponibilidade tem custo direto (verba de anúncio desperdiçada).
- **Auditabilidade:** manter histórico de quem criou/editou/publicou cada landing page.

## 9. Riscos e decisões em aberto

| Tópico | Risco/decisão pendente |
|---|---|
| Domínio próprio + SSL | Configurado por tenant (não por landing page), em fluxo separado da criação de páginas. Como o sistema já roda em Docker, o caminho natural é Traefik (ou Caddy) como proxy reverso containerizado com ACME automático — simplifica bastante essa parte. Ainda assim, definir na fase de arquitetura: como a verificação de um novo domínio dispara a configuração do proxy dinamicamente (via Docker provider/labels ou arquivo de configuração dinâmica), sem exigir reiniciar a stack. |
| Bot do Telegram | Requer criar e hospedar um bot (via BotFather). Envio síncrono com timeout curto no MVP (sem fila); se o volume de leads crescer a ponto de a latência da API do Telegram afetar a resposta ao visitante, reavaliar fila assíncrona (Celery/RQ). |
| LGPD | Adiado para fase futura por decisão do time, mas como o sistema coleta dados pessoais (nome, e-mail, telefone) de terceiros, é um risco de compliance que deve ser endereçado **antes de operar com leads reais em produção**, não só "quando der tempo". |
| Anti-spam | MVP usa honeypot + rate limit; se houver spam significativo, avaliar captcha (ex: Cloudflare Turnstile) em fase futura. |
| Billing | Fora de escopo — mas se o sistema for lançado para múltiplos clientes reais, vai precisar de algum controle de uso antes ou depois do lançamento comercial. |
| SQLite em produção | Adequado para o início (baixo volume, um único container da app). Limita escala horizontal (não suporta múltiplas réplicas da app escrevendo ao mesmo tempo) e exige volume persistente configurado corretamente. Migrar para Postgres quando o volume de leads/tráfego justificar. |

## 10. Stack técnica

- **Backend:** Python/Django.
- **Frontend:** Django Templates + HTMX (interatividade servidor-driven) + Alpine.js (estado client-side leve) + Tailwind CSS (estilização utilitária, tanto no site público quanto no painel). Sem SPA/framework JS pesado.
- **Notificação Telegram:** chamada HTTP síncrona com timeout curto, sem fila/broker no MVP (ver seção 9).
- **Banco de dados:** SQLite no início (simplicidade, sem serviço extra). Como roda em container, o arquivo do banco precisa ficar em volume Docker persistente (não no filesystem efêmero do container) para não perder dados a cada rebuild/deploy. Migrar para Postgres é o caminho natural se/quando surgir necessidade de acesso concorrente mais pesado ou múltiplas réplicas da app — reavaliar quando o volume de uso justificar.
- **Infraestrutura/deploy:** aplicação containerizada (Docker), rodando via `docker-compose` (ou orquestrador a definir). Serviços esperados: app Django e proxy reverso (banco embutido via SQLite, sem serviço próprio por enquanto).
- **Domínio custom + SSL:** proxy reverso containerizado com ACME automático (ex: Traefik com provider Docker), emitindo um certificado por domínio de tenant verificado — sem configuração manual por cliente. É a opção natural dado que tudo já roda em Docker; alternativa seria Caddy no mesmo modelo.
- **Armazenamento de mídia:** uploads de imagens/vídeo em volume Docker/bind mount em dev; object storage tipo S3-compatível em produção (evita depender de disco local do container, que é efêmero).

## 11. Modelo de dados (alto nível)

- `Tenant` (conta) — `slug` (usado no fallback `meusaas.com/<slug>/...`) + `custom_domain` + `domain_verified`
- `Tenant` — 1:N `User`
- `Tenant` — 1:N `LandingPage`
- `LandingPage` — campos das 10 seções (hero, galeria, condições, requisitos, características, vídeo, CTA) + `status` (rascunho/publicada) + `slug` + IDs de tracking (pixel/ads)
- `LandingPage` — 1:N `LeadFormField` (se os campos do formulário forem configuráveis) — no MVP pode começar fixo (nome, e-mail, telefone, cidade) e evoluir para configurável
- `LandingPage` — 1:N `Lead`
- `Lead` — dados do formulário + UTM capturados + `status` + timestamps
- `Lead` — 1:N `LeadStatusHistory`
- `Tenant` — 1:1 `TelegramIntegration` (chat_id vinculado)

## 12. Fluxos principais

1. **Criar e publicar landing page:** login → "Nova landing page" → preencher as 10 seções → salvar rascunho → publicar (fica disponível em `meusaas.com/<slug-do-tenant>/<slug-da-página>` ou no domínio próprio, se já configurado). Configurar domínio próprio é um fluxo à parte, em "Configurações da conta", e não bloqueia esse processo.
2. **Configurar domínio próprio (opcional, feito uma vez por tenant):** "Configurações da conta" → informar domínio → seguir instruções de DNS → "verificar domínio" → SSL emitido automaticamente → todas as landing pages do tenant (existentes e futuras) passam a responder também nesse domínio.
3. **Captura de lead:** visitante clica em anúncio → cai na landing page (UTM capturado) → preenche formulário → HTMX envia sem reload → lead salvo → notificação Telegram enviada de forma síncrona com timeout curto.
4. **Gestão de lead:** usuário recebe notificação no Telegram → abre o painel → encontra o lead → atualiza status conforme avança no atendimento → exporta lista quando necessário.

## 13. Fora do escopo deste documento

- Especificação visual pixel-a-pixel (wireframes detalhados) — a ser refinado com o design a partir do exemplo fornecido.
- Especificação de API pública/webhooks para integrações externas.
- Estratégia de precificação e planos comerciais.
