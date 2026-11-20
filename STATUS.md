# STATUS — gta6-trophy-rarity-forecast-01 (forecaster trophy GTA VI)

Tanggal: 20 Nov 2026 ~13:20 WIB. Deadline bounty: 21 Nov 2026 18:30 WIB.
Akun: make.fun @turibaru. Entri ini BELUM di-submit.

## Yang sudah dibangun

Lokasi: `~/workspace/makefun/entries/gta6-trophy-rarity-forecast-01/`

- `main.py` — program Python 3.13, stdlib saja, offline, deterministik, tanpa
  network, tanpa model. Membaca case `makefun/gta6-trophies-case/v1` dan
  menulis 5 kuantil (5/25/50/75/95%) per trophy (55 trophy) sesuai format kit.
- `LICENSE` — MIT (disalin dari starter kit).
- `README.md` — penjelasan model + hasil uji.

### Pendekatan forecasting

Halaman Exophase adalah snapshot basi: hanya berubah saat Exophase refresh
(jam-an), dan saat refresh jumlah pemain terlacak melonjak sementara tiap rate
terdilusi pemain baru. Dua rezim:

1. **Ada refresh di histori (kasus final):** per trophy, fit `log(rate)` vs
   `ln(1 + jam sejak rilis)` pada snapshot berbeda di jendela 36 jam terakhir
   (WLS, bobot resensi), lalu perubahan hasil fit dari bacaan terakhir
   **diredam** `1/(1 + x_target - x_last)` — tren launch-night bersifat
   cekung (rate jenuh), garis lurus yang diekstrapolasi 4,5 hari akan
   overshoot (terbukti di uji sintetis v1: median 2x jawaban).
2. **Tidak ada refresh sama sekali (kasus practice, semua bacaan identik):**
   halaman basi + refresh overdue — jumlah pemain diproyeksi tumbuh ikut pace
   launch yang dipublikasikan house sendiri (638 → 3.868 pemain, doubling
   ~2 jam, diukur dari bacaan pertama, cap 12x), earners ditahan datar,
   sehingga tiap rate terdilusi. Trophy ~100% mengikuti jumlah pemain.

Spread logit per trophy = random walk (0,5/sqrt-hari) + ketidakpastian prediksi
fit + noise hitungan trophy langka + risiko refresh (besar saat belum pernah
ada refresh). Kuantil = `inv_logit(logit(median) + z_tau * sigma)`.

## Hasil uji vs baseline

Kit TIDAK menyertakan jawaban practice, jadi jawaban direkonstruksi dari
agregat yang dipublikasikan `competition.yaml` (bacaan 04:30Z: 3.868 pemain,
4.276 trophy; earners launch-night bilangan bulat eksak karena rate = k/638).
Validasi rekonstruksi: baseline starter mendapat 1,40–1,69, mengapit 1,51 yang
dipublikasikan rules — rekonstruksi kredibel. Dua varian alokasi 103 trophy
baru (proporsional / nol) diuji.

| Uji | Baseline naif (rate tetap) | Entri ini |
|---|---|---|
| Practice p00+p01 (rekonstruksi) | 1,40–1,69 (miss 0,68pp, cov 0,00) | **0,31–0,32** (miss 0,03pp, cov 0,98) |
| Final sintetis dunia A (N power-law, rate jenuh) | 0,29 | **0,25** |
| Final sintetis dunia B (N jenuh, rate power-law) | 0,40 | **0,30** |
| Final sintetis dunia C (N exp-lalu-datar, rate ramp-lalu-datar) | 0,38 | **0,29** |

Deterministik (run ulang byte-identik), ~0,09 dtk per case (batas 8 dtk),
output valid (55 baris, kuantil non-decreasing, ≤65.536 byte). Edge case
(histori 1 bacaan, rate null, semua rate 0) semua jalan bersih.
Skrip evaluasi (bukan bagian repo): `/tmp/gta6eval/eval.py`.

## Yang MASIH KURANG untuk submit

1. **Repo GitHub publik** — belum dibuat. Harus dibuat SETELAH bounty dibuka
   (19 Nov 2026 11:30 UTC — sudah lewat, jadi boleh sekarang), berisi
   `main.py` + `LICENSE` + `README.md` (+ `STATUS.md` opsional), satu commit.
   Perlu GitHub PAT / akses akun GitHub Adi — JANGAN buat tanpa persetujuan Adi.
2. **Bundle transcript** — entri wajib menyertakan transkrip sesi agen yang
   membangunnya (`node cli/makefun.mjs bundle` dari kit + `--muse-usage`
   untuk sesi Muse). Bundle dibuat dari agen top-level SETELAH semua subagent
   selesai; sesi ini (subagent) harus ikut terbawa. Belum dibuat.
3. **Submit via CLI/API make.fun** — butuh API key akun @turibaru
   (`makefun login` / kredensial di `~/.makefun/`) + tanda tangan wallet
   Solana untuk entry message. Belum dilakukan; JANGAN submit tanpa
   instruksi Adi.
4. **Catatan risiko:** skor practice yang bagus sebagian datang dari prior
   refresh yang dikalibrasi ke angka agregat practice yang dipublikasikan —
   prior itu TIDAK akan aktif di kasus final (histori final pasti berisi
   banyak refresh), jadi tidak ada kebocoran ke final; tapi keunggulan di
   final (dunia sintetis) lebih kecil (~0,05–0,10 loss) dan dunia sintetis
   hanyalah tebakan dinamika nyata — hasil final sebenarnya baru diketahui
   setelah 26 Nov 2026.
