# Stablecoins — Overview técnico y de mercado

## ¿Qué es una stablecoin?

Una stablecoin es un activo digital diseñado para mantener un valor estable —usualmente atado 1:1 a una moneda fiduciaria (USD, EUR) o a una canasta de activos. Es la pieza que conecta el mundo cripto con la economía real: sirve como medio de pago, store of value y unidad de cuenta sin la volatilidad de BTC o ETH.

## Tipos principales

### 1. Fiat-collateralized
Respaldadas por reservas en moneda fiat (efectivo + bonos del tesoro a corto plazo).

- **USDC (Circle)**: emisor regulado en EE.UU. Reservas auditadas mensualmente. Listado en +100 exchanges. Capitalización ~$30B (varía).
- **USDT (Tether)**: la más grande por volumen (~$110B+). Históricamente menos transparente; ha mejorado sus attestations.
- **PYUSD (PayPal)**: lanzada en 2023. Reservas en bonos USD + cash. Distribución vía la app de PayPal.

### 2. Crypto-collateralized
Respaldadas con cripto sobre-colateralizado (típicamente >150% del valor emitido).

- **DAI (MakerDAO)**: respaldada por ETH, USDC y otros activos. Sistema de vaults con liquidaciones automáticas. La pionera del modelo descentralizado.

### 3. Algorithmic (advertencia)
Sin colateral real; mantienen el peg por algoritmos de oferta/demanda. **Riesgo histórico alto**: Terra/UST colapsó en mayo 2022 ($40B+ destruidos).

## Tecnología subyacente

- Corren en blockchains EVM (Ethereum, Polygon, Arbitrum, Base, Optimism), Solana, Tron y otras.
- Cada stablecoin tiene contratos en múltiples chains (USDC tiene 16+ versiones nativas).
- **Bridges** mueven stablecoins entre chains pero introducen riesgo (Wormhole, Multichain han sido explotados).
- **CCTP de Circle**: bridge nativo para USDC entre chains soportadas — mucho más seguro que bridges genéricos.

## Casos de uso reales en LatAm

1. **Remesas**: enviar USDC desde EE.UU. a Argentina/Colombia/Venezuela cuesta centavos vs ~5-7% con Western Union.
2. **Ahorro en USD**: usuarios en países con inflación alta acceden a dólares sin cuenta bancaria USA.
3. **Pagos B2B cross-border**: freelancers y empresas reciben pagos sin esperar 3-5 días de SWIFT.
4. **DeFi**: lending, yield farming, swaps — todo se denomina en stablecoins.

## Regulación

- **EE.UU.**: GENIUS Act (2024) establece marco federal. Stablecoins emitidas por entidades reguladas.
- **EU**: MiCA (Markets in Crypto-Assets Regulation) entró en vigor en 2024. Restringe stablecoins no respaldadas en EUR.
- **LatAm**: marcos en evolución. Brasil con regulación clara, Argentina con foco en stablecoins (BCRA), México con la Ley Fintech.

## Compliance & ops para una fintech sobre stablecoins

### KYC/AML
- Verificación de identidad en onboarding (liveness check, OCR de documento, sanctions screening).
- Monitoreo continuo de transacciones contra listas (OFAC, ONU, locales).
- Análisis on-chain de wallets contraparte (Chainalysis, TRM Labs, Elliptic).

### Conciliación
- Cada movimiento on-chain debe matchearse con un movimiento contable off-chain.
- LLMs son útiles para extraer datos no estructurados de memos, comprobantes y screenshots de usuarios.
- Detección de discrepancias: tx confirmadas sin booking, bookings sin tx, deltas de fee, etc.

### Riesgo
- **Smart contract risk**: el contrato del token puede tener bugs o ser pausado por el emisor.
- **Depeg risk**: USDC se depegó brevemente a $0.87 en marzo 2023 por exposición a SVB. Recuperó en 2 días.
- **Counterparty risk**: si el emisor (Circle, Tether) tiene problemas, todas las stablecoins de ese emisor se ven afectadas.

### Treasury
- Hot wallets para liquidez operativa diaria; multi-sig para reservas.
- Diversificación entre stablecoins para no concentrar riesgo en un solo emisor.
- Hedging cuando aplica (raro, las stablecoins son el hedge en sí).

## Por qué importa para IA

Las operaciones de una fintech sobre stablecoins son **intensivas en texto no estructurado**:

- Soporte multilingüe a usuarios en 150+ países.
- Comprobantes, memos, screenshots, mensajes de WhatsApp que el equipo de ops procesa manualmente.
- Compliance reports que requieren narrativa, no solo datos.
- Detección de fraude que combina señales on-chain + comportamentales.

Esto es **terreno fértil para LLMs**: extracción estructurada, clasificación, summarization, deflexión de soporte Tier-1, asistentes para analistas de compliance.

## Fuentes y referencias

- [Circle Transparency Reports](https://www.circle.com/en/transparency)
- [MakerDAO documentation](https://docs.makerdao.com/)
- [Chainalysis Crypto Crime Reports](https://www.chainalysis.com/reports/)
- [BIS Working Paper on Stablecoins](https://www.bis.org/publ/work905.htm)
