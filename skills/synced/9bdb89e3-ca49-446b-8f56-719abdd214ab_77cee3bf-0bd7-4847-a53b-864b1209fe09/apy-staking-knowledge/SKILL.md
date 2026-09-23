---
name: apy-staking-knowledge
description: >
  Reference for computing Solana staking APY metrics from BigQuery for Marinade Finance products.
  Use this skill whenever the user asks about APY, SSI, SSR, staking rates, epoch rewards,
  validator performance, Marinade Native APY, Marinade Select APY, staking yield calculations,
  or wants to write BigQuery queries against the mainnet_beta_stakes dataset.
  Also trigger when the user mentions epoch rewards, staker rewards, MEV rewards, inflation rewards,
  PSR settlements, institutional settlements, protected staking rewards, or stake account states
  (active, activating, deactivating). Trigger even for casual mentions like "what APY are we getting"
  or "how does the staking rate compare".
---

# Solana staking APY — BigQuery knowledge base

## BigQuery access

Project: `data-store-406413`
Dataset: `mainnet_beta_stakes`

All queries must use fully qualified table names: `` `data-store-406413.mainnet_beta_stakes.<table>` ``

Use the BQ MCP tools (`BQ MCP:execute_sql_readonly`, `BQ MCP:list_table_ids`, etc.) to query data.

## Stake account states

A Solana stake account has three balance fields that describe its lifecycle:

| Field | Meaning |
|---|---|
| `active` | Stake that is fully delegated and earning rewards this epoch |
| `activating` | Stake that has been delegated but is not yet earning — becomes `active` next epoch |
| `deactivating` | Stake that is being undelegated — **still a subset of `active`** and still earns rewards this epoch; becomes inactive next epoch |

**Critical**: `deactivating` is NOT additive to `active`. When a user deactivates 1 SOL of fully active stake, the snapshot shows `active = 1, deactivating = 1`. That SOL still earns rewards during the deactivation epoch. Next epoch it becomes inactive (active = 0, deactivating = 0).

`balance ≈ active + activating + rent_exempt_reserve`

The `balance` field should not be used for APY calculations. It includes rent-exempt reserves (~0.00228 SOL per account) and mixes earning/non-earning stake.

## Epoch times

Epoch timestamps come from the `epochs` table. **Never estimate epoch times or durations** — always query them.

```sql
SELECT epoch, epoch_end_time
FROM `data-store-406413.mainnet_beta_stakes.epochs`
ORDER BY epoch DESC
LIMIT 10
```

The APY formula requires actual seconds between epochs, not an assumed duration.

## Marinade authority model

Marinade uses separate authorities to distinguish between system-managed stake and user-requested unstakes.

### Max Yield (Native / Bidding)

| Role | Public Key |
|---|---|
| Stake authority | `stWirqFCf2Uts1JBL1Jsd3r6VBWhgnpdPxCTe1MFjrq` |
| Exit authority | `ex9CfkBZZd6Nv9XdnoDmmB45ymbu4arXVk7g5pWnt3N` |

### Select (Institutional)

| Role | Public Key |
|---|---|
| Stake authority | `STNi1NHDUi6Hvibvonawgze8fM83PFLeJhuGMEXyGps` |
| Exit authority | `EX1Fs34ajye3BTMSjTkMdZ8P4hb99vQFWzmueqhKGpH6` |

### How authorities separate user vs system actions

- **User unstakes**: Marinade changes stake authority from the main authority to the exit authority, then deactivates. The account disappears from queries filtered on the main stake authority.
- **Marinade re-delegates** (moves stake between validators): The stake authority stays the same. Deactivating stake on the old validator appears in queries filtered on the main stake authority.

This means: when querying by stake authority, any `deactivating` balance you see is **always from Marinade's own rebalancing**, never from user withdrawals. User withdrawals are invisible because they use a different authority.

## The denominator problem for Native APY

Marinade's rebalancing creates a one-epoch dead zone:
- **Epoch N**: stake on old validator has `active = X, deactivating = X` → earns rewards, visible in query
- **Epoch N+1**: same SOL appears as `activating = X` on new validator → earns nothing, still visible in query
- **Epoch N+2**: `active = X` on new validator → earns again

The apy-api code uses `active + deactivating` as the denominator for Native:

```sql
SUM(COALESCE(deactivating, 0) + COALESCE(active, 0)) / 1e9 AS stake
```

Since `deactivating` is a subset of `active`, this **double-counts** the deactivating SOL in the denominator. This is intentional — it pre-penalises the epoch rate to compensate for the dead epoch that follows. Without this, the rolling APY would overstate what stakers actually earn, because it would not account for the rebalancing inefficiency.

## APY concepts

### 1. SSI / SSR (Solana Staking Index / Solana Staking Rate)

The whole-network baseline. Total rewards generated (staker inflation + validator inflation + block rewards) divided by total active stake across all validators. Excludes MEV.

**0/0 baseline** (staker benchmark): `(staker_inflation + validator_inflation + staker_mev + validator_mev) / total_active_stake`. This is what a staker earns from a 0% commission validator — all inflation + MEV passed through, but block rewards kept by validator. The 0/0 line sits below SSI by the network-average block reward per SOL. Use 0/0 as the staker benchmark; use SSI as the total-value benchmark.

```sql
WITH epoch_data AS (
  SELECT
    s.epoch,
    e.epoch_end_time,
    SUM(COALESCE(s.active, 0)) / 1e9 AS total_active_stake
  FROM `data-store-406413.mainnet_beta_stakes.stakes` s
  INNER JOIN `data-store-406413.mainnet_beta_stakes.epochs` e ON s.epoch = e.epoch
  WHERE s.epoch BETWEEN @minEpoch AND @maxEpoch
  GROUP BY s.epoch, e.epoch_end_time
),
staker_inflation AS (
  SELECT epoch, SUM(COALESCE(amount, 0)) / 1e9 AS amount
  FROM `data-store-406413.mainnet_beta_stakes.rewards_inflation`
  WHERE epoch BETWEEN @minEpoch AND @maxEpoch
  GROUP BY epoch
),
validator_inflation AS (
  SELECT epoch, SUM(COALESCE(amount, 0)) / 1e9 AS amount
  FROM `data-store-406413.mainnet_beta_stakes.rewards_validators_inflation`
  WHERE epoch BETWEEN @minEpoch AND @maxEpoch
  GROUP BY epoch
),
validator_blocks AS (
  SELECT epoch, SUM(COALESCE(amount, 0)) / 1e9 AS amount
  FROM `data-store-406413.mainnet_beta_stakes.rewards_validators_blocks`
  WHERE epoch BETWEEN @minEpoch AND @maxEpoch
  GROUP BY epoch
)
SELECT
  ed.epoch,
  ed.epoch_end_time,
  ed.total_active_stake,
  COALESCE(si.amount, 0) + COALESCE(vi.amount, 0) + COALESCE(vb.amount, 0) AS total_rewards,
  (COALESCE(si.amount, 0) + COALESCE(vi.amount, 0) + COALESCE(vb.amount, 0))
    / ed.total_active_stake AS epoch_rate
FROM epoch_data ed
LEFT JOIN staker_inflation si USING(epoch)
LEFT JOIN validator_inflation vi USING(epoch)
LEFT JOIN validator_blocks vb USING(epoch)
ORDER BY ed.epoch DESC
```

### 2. Validator staker APY

What a delegator earns from a specific validator, after the validator takes commission. Rewards = staker inflation + staker MEV. Denominator = total active stake on that validator.

**Validator total APY** adds the validator's own income (commission from inflation, MEV commission, block rewards) to show total value generated.

### 3. Marinade Native (Bidding / Max Yield) APY

Authority: `stWirqFCf2Uts1JBL1Jsd3r6VBWhgnpdPxCTe1MFjrq`

Rewards per epoch = inflation + MEV + bid auction winnings + PSR settlements.
Denominator = `active + deactivating` (see denominator section above).

```sql
WITH stakers_rewards AS (
  SELECT
    stakes.epoch,
    SUM((COALESCE(deactivating, 0) + COALESCE(active, 0)) / 1e9) stake,
    SUM(COALESCE(inflation.amount, 0) / 1e9) inflation,
    SUM(COALESCE(mev.amount, 0) / 1e9) mev
  FROM `data-store-406413.mainnet_beta_stakes.stakes` stakes
    LEFT JOIN `data-store-406413.mainnet_beta_stakes.rewards_inflation` inflation
      ON stakes.stake_account = inflation.stake_account AND stakes.epoch = inflation.epoch
    LEFT JOIN `data-store-406413.mainnet_beta_stakes.rewards_mev` mev
      ON stakes.stake_account = mev.stake_account AND stakes.epoch = mev.epoch
  WHERE stakes.epoch BETWEEN @minEpoch AND @maxEpoch
    AND stakes.stake_authority = 'stWirqFCf2Uts1JBL1Jsd3r6VBWhgnpdPxCTe1MFjrq'
  GROUP BY stakes.epoch
),
psr AS (
  SELECT
    epoch,
    SUM(CASE WHEN reason = '"Bidding"' THEN amount / 1e9 ELSE 0 END) AS bids,
    SUM(CASE WHEN reason <> '"Bidding"' THEN amount / 1e9 ELSE 0 END) AS psr
  FROM `data-store-406413.mainnet_beta_stakes.psr_settlements`
  WHERE epoch BETWEEN @minEpoch AND @maxEpoch
    AND stake_authority = 'stWirqFCf2Uts1JBL1Jsd3r6VBWhgnpdPxCTe1MFjrq'
  GROUP BY epoch
)
SELECT
  sr.epoch,
  sr.stake,
  sr.inflation + sr.mev + COALESCE(p.bids, 0) + COALESCE(p.psr, 0) AS total_rewards,
  (sr.inflation + sr.mev + COALESCE(p.bids, 0) + COALESCE(p.psr, 0)) / sr.stake AS epoch_rate
FROM stakers_rewards sr
LEFT JOIN psr p USING(epoch)
ORDER BY sr.epoch DESC
```

### 4. Marinade Select (Institutional) APY

Select uses two authorities — **both must be included** when counting Select stake:
- Stake authority: `STNi1NHDUi6Hvibvonawgze8fM83PFLeJhuGMEXyGps` — actively managed stake
- Exit authority: `EX1Fs34ajye3BTMSjTkMdZ8P4hb99vQFWzmueqhKGpH6` — stake marked for user withdrawal (still earning until deactivated)

Select stakes into a curated set of validators (from `institutional_validators` table). The APY calculation:

1. Compute `select_stake` = sum of `active` for both STNi1 and EX1Fs authorities on Select validators
2. Compute `select_ratio = select_stake / total_stake_in_validators`
3. `select_staker_rewards = select_ratio × total_stakers_rewards` (pro-rata share of inflation + MEV)
4. Add staker settlement payouts from `institutional_settlements`
5. `raw_apy = (1 + (select_staker_rewards + staker_settlements) / select_stake) ^ (sec_per_year / epoch_duration) - 1`

#### Settlement structure in `institutional_settlements`

The settlement mechanism redistributes validator gross (commission + block rewards) according to fee config. Three settlement authorities:

| Authority | Role | Description |
|---|---|---|
| `STNi1NHDUi6Hvibvonawgze8fM83PFLeJhuGMEXyGps` | Staker payouts | Settlements to Select stakers (various withdraw_authorities = individual users) |
| `EX1Fs34ajye3BTMSjTkMdZ8P4hb99vQFWzmueqhKGpH6` | Staker payouts (exiting) | Settlements to stakers who requested unstake |
| `mDAo14E6YJfEHcVZLcc235RVjviypmKMhftq7jeiLJz` | Marinade fee | Marinade's distributor fee |

Staker settlement total = STNi1 settlements + EX1Fs settlements.

#### Fee config

Fetch actual fees from: `https://institutional-staking.marinade.finance/v1/configs/epoch?from_epoch=N&to_epoch=N`

As of epoch 954: `validator_fee_bps = 10`, `distributor_fee_bps = 30`. These are NOT hardcoded — always query the API or derive from actual settlement data in BigQuery.

#### Three-party economics (per validator)

The settlement mechanism is precise — for each validator:
- **Validator gross** = `select_ratio × (val_inflation + val_mev + val_blocks)` — includes block rewards
- **Validator net** = validator gross − staker settlements − Marinade settlements = exactly `validator_fee_bps` worth
- **Marinade fee** = settlement to `mDAo14E6YJfEHcVZLcc235RVjviypmKMhftq7jeiLJz` ≈ `distributor_fee_bps` worth
- **Staker gets** = pro-rata(staker_inflation + staker_mev) + staker settlements = everything else

The settlements equalise validator economics: regardless of commission rate, every Select validator nets the same `validator_fee_bps` after settlements. High-commission validators pay more in settlements; 0% commission validators pay less — but the net is identical.

### 5. Liquid staking APY (mSOL, JitoSOL, etc.)

Cannot be computed from BigQuery stake data. Liquid staking pools rebalance through a single program authority, making it impossible to separate pool rebalancing from user redemptions. Additionally, the pool reserve (liquid SOL held for instant unstakes) is not in the stakes table at all.

Liquid APY is derived from the **token exchange rate** (e.g. mSOL/SOL price) over time using CSV price data.

## Rolling APY formula

The apy-api computes rolling APY using a cumulative "price" curve:

1. For each epoch, compute `bump = (rewards + stake) / stake`
2. Build a cumulative price: `price[n] = price[n-1] × bump[n]`, starting at 1.0
3. For a given rolling window, annualise: `APY = (price_upper / price_lower) ^ (SECONDS_IN_YEAR / (time_upper - time_lower)) - 1`

Where `SECONDS_IN_YEAR = 365.25 × 24 × 3600 = 31,557,600`

The times (`time_upper`, `time_lower`) are **actual epoch_end_time values from the epochs table**, converted to Unix seconds.

For a quick single-epoch APY estimate (not the rolling window approach):
`APY = (1 + epoch_rate) ^ epochs_per_year - 1`

Where `epochs_per_year ≈ 182.625` (from `SECONDS_PER_YEAR / (0.4 × 432000)`), but the rolling approach using real timestamps is more accurate.

## BigQuery tables reference

| Table | Key columns | Description |
|---|---|---|
| `epochs` | `epoch`, `epoch_end_time` | Epoch boundary timestamps |
| `stakes` | `epoch`, `stake_account`, `stake_authority`, `withdraw_authority`, `vote_account`, `balance`, `active`, `activating`, `deactivating` | Per-account per-epoch stake state |
| `rewards_inflation` | `epoch`, `stake_account`, `amount` | Inflation rewards distributed to stakers |
| `rewards_mev` | `epoch`, `stake_account`, `amount` | MEV rewards distributed to stakers |
| `rewards_validators_inflation` | `epoch`, `vote_account`, `amount` | Validator commission from inflation |
| `rewards_validators_mev` | `epoch`, `vote_account`, `amount` | Validator MEV commission |
| `rewards_validators_blocks` | `epoch`, `vote_account`, `amount` | Validator block production rewards |
| `psr_settlements` | `epoch`, `stake_authority`, `withdraw_authority`, `amount`, `reason` | Protected Staking Rewards settlements for Native/Bidding |
| `institutional_settlements` | `epoch`, `stake_authority`, `withdraw_authority`, `vote_account`, `amount`, `reason` | Settlement payouts for Select |
| `institutional_validators` | `epoch`, `vote_account` | Validators in the Select program per epoch |
| `stake_pools` | `name`, `stake_authorities` | Maps stake authorities to named pools (Marinade, Jito, etc.) |

All `amount` columns in rewards tables are in **lamports** (divide by 1e9 for SOL). The `active`, `activating`, `deactivating`, `balance` columns in `stakes` are also in lamports.

## Key public keys

| Entity | Public Key |
|---|---|
| Native stake authority | `stWirqFCf2Uts1JBL1Jsd3r6VBWhgnpdPxCTe1MFjrq` |
| Native exit authority | `ex9CfkBZZd6Nv9XdnoDmmB45ymbu4arXVk7g5pWnt3N` |
| Select stake authority | `STNi1NHDUi6Hvibvonawgze8fM83PFLeJhuGMEXyGps` |
| Select exit authority | `EX1Fs34ajye3BTMSjTkMdZ8P4hb99vQFWzmueqhKGpH6` |
| Marinade Liquid stake authority | `4bZ6o3eUUNXhKuqjdCnCoPAoLgWiuLYixKaxoa8PpiKk` |
| Recipes stake authority | `stRcP4kVnCNubspkcP3BXEthPfZFEriQBqSczDDwmYH` |
| Recipes exit authority | `exRcSuzu5XLZYZ4GgeWYDn9qYwQnBycmyG8zBDJhEgY` |
| Marinade fee receiver (Select) | `mDAo14E6YJfEHcVZLcc235RVjviypmKMhftq7jeiLJz` |
| Marinade bid revenue receiver | `mDAo14E6YJfEHcVZLcc235RVjviypmKMhftq7jeiLJz` |
| Marinade revenue wallet | `89SrbjbuNyqSqAALKBsKBqMSh463eLvzS4iVWCeArBgB` |
| Marinade revenue wallet | `BBaQsiRo744NAYaqL3nKRfgeJayoqVicEQsEnLpfsJ6x` |

## How Marinade earns revenue

Marinade's revenue flows through two separate mechanisms depending on the product:

### Native (Bidding / Max Yield) — SAM auction revenue

Validators bid in the Stake Auction Marketplace (SAM) for Native stake allocation. The bid payments are recorded in `psr_settlements` and split:
- **To stakers** (~5-60%): recorded with `stake_authority = stWirqFCf2Uts1JBL1Jsd3r6VBWhgnpdPxCTe1MFjrq`, various `withdraw_authority` (individual users). Included in Native APY.
- **To Marinade** (~40-95%): recorded with `stake_authority = mDAo14E6YJfEHcVZLcc235RVjviypmKMhftq7jeiLJz` AND `withdraw_authority = mDAo14E6YJfEHcVZLcc235RVjviypmKMhftq7jeiLJz` (`stake_authority = withdraw_authority`). NOT included in Native APY — separate revenue flow.

Marinade's bid revenue (~170-230 SOL/epoch as of epoch 954) is the primary Native revenue source. The `mDAo` authority has zero active stake — it's a pure revenue-receiving wallet.

Query to find Marinade's SAM revenue:
```sql
SELECT epoch, SUM(amount) / 1e9 AS revenue_sol
FROM `data-store-406413.mainnet_beta_stakes.psr_settlements`
WHERE reason = '"Bidding"'
  AND withdraw_authority IN ('89SrbjbuNyqSqAALKBsKBqMSh463eLvzS4iVWCeArBgB',
                             'mDAo14E6YJfEHcVZLcc235RVjviypmKMhftq7jeiLJz',
                             'BBaQsiRo744NAYaqL3nKRfgeJayoqVicEQsEnLpfsJ6x')
  AND stake_authority = withdraw_authority
GROUP BY epoch ORDER BY epoch DESC
```

### Select (Institutional) — settlement-based distributor fee

The settlement mechanism splits validator gross (commission + block rewards) three ways:
- **To stakers**: `institutional_settlements` where `stake_authority IN (STNi1..., EX1Fs...)`
- **To Marinade**: `institutional_settlements` where `stake_authority = mDAo14E6YJfEHcVZLcc235RVjviypmKMhftq7jeiLJz`
- **Validator keeps**: the remainder (= `validator_fee_bps` from config)

The Marinade fee is already excluded from staker settlements at the settlement level. Do NOT subtract it again from the APY.

## Common pitfalls

1. **Never use `balance` for APY denominators** — it includes rent and mixes earning/non-earning stake.
2. **Never estimate epoch duration** — query `epochs` table for actual `epoch_end_time` values.
3. **`deactivating` is a subset of `active`**, not additive. Don't sum all three fields expecting them to equal `balance`.
4. **Native denominator is `active + deactivating`** to account for rebalancing inefficiency. This intentionally double-counts deactivating stake.
5. **Select stake must include BOTH authorities** — the stake authority (`STNi1...`) AND exit authority (`EX1Fs...`). The exit authority holds stake that users requested to unstake but is still earning. Omitting it undercounts Select stake.
6. **When querying by stake authority**, user-initiated unstakes are invisible (they use the exit authority). All `deactivating` visible under the main authority is from Marinade's system rebalancing.
7. **Liquid staking APY cannot be computed from BigQuery** — use token price data instead.
8. **Always show full public keys** — never truncate vote accounts, stake authorities, or stake account addresses.
9. **Select validator gross MUST include block rewards** — `val_inflation + val_mev + val_blocks`. Omitting block rewards makes validator net appear negative when it should be positive (equal to `validator_fee_bps`).
10. **Select fees come from actual settlement data**, not config estimates. Query `institutional_settlements` grouped by `stake_authority` to get real Marinade fee (`mDAo14E6YJfEHcVZLcc235RVjviypmKMhftq7jeiLJz`) and staker settlements. The API config at `https://institutional-staking.marinade.finance/v1/configs/epoch` gives the target bps but actual settlements may differ slightly.

## Per-validator reward breakdown charts

A useful analysis pattern: compute SOL earned **per 1M SOL staked** per epoch, broken into three reward sources. This normalises across validators of different sizes.

The three sources, in display order for stacked bars:
1. **Inflation** = `rewards_inflation` (staker) + `rewards_validators_inflation` (validator commission)
2. **Block rewards** = `rewards_validators_blocks`
3. **MEV** = `rewards_mev` (staker) + `rewards_validators_mev` (validator commission)

Each source is divided by `active` stake on that validator and multiplied by 1e6 to get per-1M-SOL values.

### Reference lines for charts

Two benchmark lines should be included on reward breakdown charts:

**SSI line** = `(staker_inflation + validator_inflation + block_rewards) / total_active_stake × 1e6`. This is the total value generated per SOL across the whole network, excluding MEV. Useful on the "total APY" chart (staker + validator combined).

**0/0 line** = `(staker_inflation + validator_inflation + staker_mev + validator_mev) / total_active_stake × 1e6`. This represents what a staker would earn from a hypothetical 0% commission validator that shares 100% of inflation and MEV but keeps 100% of block rewards. This is the correct staker benchmark — stakers don't receive block rewards, so SSI overstates what they can earn. The gap between SSI and 0/0 equals the network-average block rewards per SOL.

```sql
-- Compute both lines for a given epoch
WITH s AS (
  SELECT SUM(COALESCE(active, 0)) / 1e9 AS active
  FROM `data-store-406413.mainnet_beta_stakes.stakes` WHERE epoch = @epoch
),
si AS (SELECT SUM(COALESCE(amount, 0)) / 1e9 AS a FROM `data-store-406413.mainnet_beta_stakes.rewards_inflation` WHERE epoch = @epoch),
sm AS (SELECT SUM(COALESCE(amount, 0)) / 1e9 AS a FROM `data-store-406413.mainnet_beta_stakes.rewards_mev` WHERE epoch = @epoch),
vi AS (SELECT SUM(COALESCE(amount, 0)) / 1e9 AS a FROM `data-store-406413.mainnet_beta_stakes.rewards_validators_inflation` WHERE epoch = @epoch),
vm AS (SELECT SUM(COALESCE(amount, 0)) / 1e9 AS a FROM `data-store-406413.mainnet_beta_stakes.rewards_validators_mev` WHERE epoch = @epoch),
vb AS (SELECT SUM(COALESCE(amount, 0)) / 1e9 AS a FROM `data-store-406413.mainnet_beta_stakes.rewards_validators_blocks` WHERE epoch = @epoch)
SELECT
  (si.a + vi.a + vb.a) / s.active * 1e6 AS ssi_per_M,
  (si.a + vi.a + sm.a + vm.a) / s.active * 1e6 AS zero_zero_per_M
FROM s, si, sm, vi, vm, vb
```

Use the 0/0 line on staker-perspective charts (where bars show pro-rata inflation + MEV + settlements). Use the SSI line on total-APY charts (where bars show all reward sources combined).

### Query pattern for Select validators

```sql
WITH select_validators AS (
  SELECT vote_account
  FROM `data-store-406413.mainnet_beta_stakes.institutional_validators`
  WHERE epoch = @epoch
),
validator_data AS (
  SELECT
    s.vote_account,
    SUM(COALESCE(s.active, 0) / 1e9) AS active,
    SUM(COALESCE(ri.amount, 0) / 1e9) AS staker_inflation,
    SUM(COALESCE(rm.amount, 0) / 1e9) AS staker_mev
  FROM `data-store-406413.mainnet_beta_stakes.stakes` s
  INNER JOIN select_validators sv ON s.vote_account = sv.vote_account
  LEFT JOIN `data-store-406413.mainnet_beta_stakes.rewards_inflation` ri
    ON s.stake_account = ri.stake_account AND s.epoch = ri.epoch
  LEFT JOIN `data-store-406413.mainnet_beta_stakes.rewards_mev` rm
    ON s.stake_account = rm.stake_account AND s.epoch = rm.epoch
  WHERE s.epoch = @epoch
  GROUP BY s.vote_account
),
vi AS (
  SELECT vote_account, SUM(amount) / 1e9 AS amount
  FROM `data-store-406413.mainnet_beta_stakes.rewards_validators_inflation` r
  INNER JOIN select_validators sv USING(vote_account)
  WHERE epoch = @epoch GROUP BY vote_account
),
vm AS (
  SELECT vote_account, SUM(amount) / 1e9 AS amount
  FROM `data-store-406413.mainnet_beta_stakes.rewards_validators_mev` r
  INNER JOIN select_validators sv USING(vote_account)
  WHERE epoch = @epoch GROUP BY vote_account
),
vb AS (
  SELECT vote_account, SUM(amount) / 1e9 AS amount
  FROM `data-store-406413.mainnet_beta_stakes.rewards_validators_blocks` r
  INNER JOIN select_validators sv USING(vote_account)
  WHERE epoch = @epoch GROUP BY vote_account
)
SELECT
  vd.vote_account,
  vd.active,
  (vd.staker_inflation + COALESCE(vii.amount, 0)) / vd.active * 1e6 AS inflation_per_M,
  (vd.staker_mev + COALESCE(vmm.amount, 0)) / vd.active * 1e6 AS mev_per_M,
  COALESCE(vbb.amount, 0) / vd.active * 1e6 AS blocks_per_M
FROM validator_data vd
LEFT JOIN vi vii USING(vote_account)
LEFT JOIN vm vmm USING(vote_account)
LEFT JOIN vb vbb USING(vote_account)
WHERE vd.active > 1
ORDER BY (inflation_per_M + mev_per_M + blocks_per_M) DESC
```

### Validator names

Fetch names from `https://institutional-staking.marinade.finance/v1/validators/latest`. The `is_institutional` field marks validators that currently receive Select stake. The `name` field has the display name.
