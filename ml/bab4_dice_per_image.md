# Acuan Bab 4: Evaluasi Dice Similarity Coefficient (DSC) terhadap Ground Truth per Citra (23 Citra Uji LUTSeg)

- **Model**: `ResNet34UNet` (`24,860,105` parameter, normalisasi `[0, 1]` via `x / 255.0`, ambang sigmoid `0.5`)
- **Rata-rata `dice_ref` (terhadap Ground Truth di `ml/reference_metrics.csv`)**: `0.710273`
- **Rata-rata `dice_backend` (terhadap Ground Truth lewat pipeline backend)**: `0.710257`
- **Selisih Absolut (`|Δ Mean Dice|`)**: `0.000017` (Ambang batas `< 0.005`)
- **Rata-rata Waktu Inferensi CPU**: `190.90 ms`

| image_id | patient | dice_ref | dice_backend | area_ref_pct | area_backend_pct |
|:---------|:--------|---------:|-------------:|-------------:|-----------------:|
| `P10T_1` | `Patient_10` | 0.917073 | 0.917135 | 12.5992 | 12.6007 |
| `P10T_2` | `Patient_10` | 0.880445 | 0.880445 | 26.3702 | 26.3702 |
| `P10T_3` | `Patient_10` | 0.931385 | 0.931352 | 21.1899 | 21.1914 |
| `P10T_4` | `Patient_10` | 0.923698 | 0.923698 | 13.8763 | 13.8763 |
| `P10T_5` | `Patient_10` | 0.941834 | 0.941603 | 9.9426 | 9.9411 |
| `P10T_6` | `Patient_10` | 0.802348 | 0.802348 | 1.8082 | 1.8082 |
| `P16T_1` | `Patient_16` | 0.893142 | 0.893192 | 17.2241 | 17.2256 |
| `P16T_2` | `Patient_16` | 0.907468 | 0.907468 | 14.5493 | 14.5493 |
| `P16T_3` | `Patient_16` | 0.860086 | 0.860086 | 15.3671 | 15.3671 |
| `P16T_4` | `Patient_16` | 0.804430 | 0.804403 | 23.1949 | 23.2040 |
| `P16T_5` | `Patient_16` | 0.807245 | 0.807205 | 15.7272 | 15.7288 |
| `P17T_1` | `Patient_17` | 0.682874 | 0.682730 | 8.9432 | 8.9417 |
| `P17T_2` | `Patient_17` | 0.682071 | 0.682071 | 7.7789 | 7.7789 |
| `P22T_1` | `Patient_22` | 0.216867 | 0.216867 | 0.3784 | 0.3784 |
| `P22T_2` | `Patient_22` | 0.143251 | 0.143349 | 2.0569 | 2.0554 |
| `P23T_1` | `Patient_23` | 0.188588 | 0.188574 | 21.6385 | 21.6415 |
| `P23T_2` | `Patient_23` | 0.797914 | 0.797947 | 10.4340 | 10.4370 |
| `P23T_3` | `Patient_23` | 0.724832 | 0.724832 | 6.6284 | 6.6284 |
| `P23T_4` | `Patient_23` | 0.459512 | 0.459512 | 2.4094 | 2.4094 |
| `P25T_1` | `Patient_25` | 0.758939 | 0.758939 | 0.5524 | 0.5524 |
| `P25T_2` | `Patient_25` | 0.769801 | 0.769801 | 3.8956 | 3.8956 |
| `P25T_3` | `Patient_25` | 0.410457 | 0.410317 | 6.7368 | 6.7398 |
| `P25T_4` | `Patient_25` | 0.832027 | 0.832027 | 1.5808 | 1.5808 |
