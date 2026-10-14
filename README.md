# KlipForge Local

KlipForge Local, uzun videolardan kısa ve paylaşılabilir klip adayları çıkaran, bunları puanlayan, yeniden kadrajlayan ve altyazılı MP4 olarak render eden yerel bir web uygulamasıdır. FastAPI backend ile derlenmiş React arayüzü aynı süreçten sunulur; varsayılan adres `http://127.0.0.1:3210` olur.

> Bu proje OpusClip ile bağlantılı değildir. Benzer bir iş akışını yerel ve şeffaf bir uygulama olarak sunar. “Virallik” puanı bir performans garantisi değil, adayları sıralamaya yardımcı olan yerel bir tahmindir.

## Gizlilik ve çevrimdışı çalışma

- Video, proje metadatası, altyazı ve render çıktıları varsayılan olarak yalnızca `data/` altında tutulur.
- Telemetri, bulut yükleme veya uzaktaki bir analiz servisi yoktur.
- Sunucu varsayılan olarak yalnızca `127.0.0.1` arayüzüne bağlanır; yerel ağdan erişime açık değildir.
- Çalışma zamanında model indirme varsayılan olarak kapalıdır (`KLIPFORGE_ALLOW_MODEL_DOWNLOAD=0`).
- `faster-whisper` modeli `models/` altında bulunuyorsa tamamen yerelden yüklenir.
- İsteğe bağlı semantik yeniden sıralama için yapılandırılan Ollama adresinin hostu `127.0.0.1`, `localhost` veya `::1` olmalıdır.
- Paket ve model indirmek isteyen kurulum adımları açıkça belirtilmiştir. Kurulum tamamlandıktan sonra uygulama internet bağlantısı olmadan çalışabilir.

Yerelde tutulması verilerin disk üzerinde şifreli olduğu anlamına gelmez. Hassas videolar için işletim sisteminin disk şifrelemesini kullanın ve `data/` klasörünün yedekleme politikasını ayrıca yönetin.

## Özellikler

- MP4, MOV, MKV, WebM, M4V, AVI, MPG ve MPEG yükleme
- FFmpeg/ffprobe ile medya doğrulama, sahne ve ses enerjisi analizi
- İsteğe bağlı `faster-whisper` ile kelime zaman damgalı yerel transkripsiyon
- Hook, akış ve değer sinyallerine göre açıklanabilir klip puanlama; çevrimdışı trend alanı şeffaf biçimde “bilinmiyor” kalır
- İsteğe bağlı yerel Ollama modeliyle, çeşitlendirilmiş en fazla 10 transkript adayını yeniden puanlama
- Hedef süre, klip sayısı, amaç, dil ve serbest metin promptu ile analiz ayarları
- 9:16, 1:1 ve 16:9 çıktı; OpenCV varsa örnek karelerdeki en büyük yüzü baz alan sabit yatay kadraj
- Impact, Clean, Boxed ve Minimal altyazı stilleri
- Klip başlangıç/bitiş, başlık, altyazı rengi, vurgu rengi ve odak konumu düzenleme
- Yerel MP4 render ve MP4/SRT indirme; arayüzde poster önizlemesi
- Proje ilerlemesi, hata durumu, yeniden deneme ve yerel proje yönetimi
- `/api` altında yerel uç nokta özeti ve `/api/openapi.json` altında makinece okunabilir OpenAPI şeması

Transkripsiyon modeli bulunmazsa uygulama kapanmaz; sahne, ses ve zaman tabanlı heuristik analizle çalışmaya devam eder. Bu durumda konuşma anlamına dayalı seçim ve altyazı kalitesi doğal olarak sınırlı olur.

## Sistem gereksinimleri

- Python 3.11 veya daha yeni
- `ffmpeg` ile `ffprobe`
- En az 4 GB RAM; `small` ve daha büyük Whisper modelleri için 8 GB+ önerilir
- Kaynak video ve render çıktıları için yeterli boş disk alanı

İndirilebilir pakette hazır arayüz bulunduğu için normal kullanımda Node.js gerekmez. Yalnızca arayüz kaynaklarını yeniden derlemek isterseniz Node.js `^20.19.0` veya `>=22.12.0` ve npm gerekir.

FFmpeg kurulumu için örnekler:

```bash
# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y python3-venv ffmpeg

# macOS (Homebrew)
brew install ffmpeg
```

Docker kullanılmaz ve gerekli değildir.

## Hızlı kurulum

### Windows 10/11

1. ZIP dosyasına sağ tıklayıp **Tümünü ayıkla** seçeneğini kullanın.
2. Çıkan `klipforge-local` klasöründeki `BASLAT-WINDOWS.bat` dosyasına çift tıklayın.
3. İlk kurulum tamamlanınca tarayıcı otomatik açılır. Siyah terminal penceresini uygulamayı kullandığınız sürece açık bırakın.

Windows başlatıcısı hazır arayüzü kullandığı için Node.js istemez. Python ortamını `uv` ile doğrulanmış Python 3.12 üzerinde hazırlar; Python/uv veya FFmpeg eksikse `winget` ile otomatik kurmak için onay ister. Yarım kalmış `.venv` klasörünü silmek yerine zaman damgalı bir yedek adına taşır ve hata olursa pencereyi kapatmadan ayrıntılı çıktıyı gösterir. FFmpeg elle kurulmak istenirse yönetici PowerShell'de şu komut kullanılabilir:

```powershell
winget install --id Gyan.FFmpeg -e
```

Kurulumdan sonra `BASLAT-WINDOWS.bat` dosyasına yeniden çift tıklayın.

### Linux, macOS veya WSL

```bash
# İndirdiğiniz ZIP'i çıkarın ve klasöre girin
cd klipforge-local
chmod +x BASLAT.sh
./BASLAT.sh
```

Ardından tarayıcıda şunu açın:

```text
http://127.0.0.1:3210
```

Başlatıcı gerekirse kurulum betiğini otomatik çalıştırır. Kurulum betiği şunları yapar:

1. `.venv` sanal ortamını oluşturur.
2. Varsayılan olarak temel ve AI Python bağımlılıklarını kurar.
3. Paketle gelen hazır frontend çıktısını kullanır; çıktı yoksa Node.js ile yeniden derler.
4. Yoksa `.env.example` dosyasını `.env` olarak kopyalar.
5. `data/` ve `models/` klasörlerini oluşturur.
6. Etkileşimli terminalde yaklaşık 150 MB'lık `base` Whisper modelini indirmeyi sorar; Enter varsayılan olarak indirmeyi onaylar.

Etkileşimsiz/CI kurulumunda model otomatik indirilmez. Kurulum sorusunu açıkça kontrol etmek için `KLIPFORGE_SETUP_DOWNLOAD_MODEL=1` (indir) veya `KLIPFORGE_SETUP_DOWNLOAD_MODEL=0` (indirme) kullanın. Hazır arayüzü kaynak koddan özellikle yeniden üretmek için `KLIPFORGE_REBUILD_FRONTEND=1` ayarlanabilir; bu durumda Node.js gerekir.

AI bağımlılıklarını istemeyen daha hafif kurulum:

```bash
KLIPFORGE_INSTALL_AI=0 KLIPFORGE_SETUP_DOWNLOAD_MODEL=0 ./scripts/setup.sh
```

## Yerel Whisper modeli

### Önerilen: kurulum sorusuyla yerel modeli hazırlamak

Normal `./scripts/setup.sh` çalıştırması etkileşimli terminalde `base` modelini (~150 MB) indirmeyi sorar; Enter “evet” kabul edilir. İndirme başarılıysa model `models/faster-whisper-base/` altına yerleşir ve sonraki uygulama çalıştırmaları çevrimdışı kalır. Model indirilemezse kurulum uyarı vererek tamamlanır ve uygulama heuristik modda çalışabilir.

Daha yüksek doğruluk için `small` modelini etkileşim sormadan açıkça indirmek:

```bash
KLIPFORGE_SETUP_DOWNLOAD_MODEL=1 \
KLIPFORGE_SETUP_MODEL_SIZE=small \
./scripts/setup.sh
```

Desteklenen kurulum boyutları: `tiny`, `base`, `small`, `medium`, `large-v3`.

| Model | Yaklaşık model boyutu | Kullanım | Not |
| --- | ---: | --- | --- |
| `tiny` | 80 MB | Hızlı deneme | Doğruluk en düşük |
| `base` | 150 MB | Kurulum sorusunun varsayılanı | Hafif CPU, hızlı başlangıç |
| `small` | 500 MB | Önerilen kalite seçeneği | Hız/doğruluk dengesi |
| `medium` | 1.5 GB | Daha yüksek doğruluk | CPU'da belirgin biçimde yavaş |
| `large-v3` | 3 GB | En yüksek doğruluk | Güçlü CPU ve yüksek RAM ister |

Mevcut backend Whisper'ı CPU üzerinde `int8` ile çalıştırır. Boyutlar yaklaşık değerlerdir; model sürümüne göre değişebilir.

### Modeli elle yerleştirmek

İnternet erişimi olan başka bir makinede CTranslate2 biçimindeki faster-whisper modelini hazırlayıp aşağıdaki gibi kopyalayabilirsiniz:

```text
models/
└── faster-whisper-small/
    ├── model.bin
    ├── config.json
    ├── tokenizer.json
    └── ...
```

Uygulama `models/faster-whisper-small`, `models/faster-whisper-base`, `models/whisper` veya doğrudan altında `model.bin` bulunan başka bir model klasörünü otomatik bulur. Alternatif olarak `.env` içinde kesin yolu belirtin:

```dotenv
KLIPFORGE_WHISPER_MODEL=./models/faster-whisper-small
```

### Çalışma zamanında açık indirme izni

Katı çevrimdışı kullanım için önerilmez. Yalnızca bilinçli olarak ağ erişimi vermek istediğiniz tek çalıştırmada kullanılmalıdır:

```bash
KLIPFORGE_WHISPER_MODEL=small \
KLIPFORGE_ALLOW_MODEL_DOWNLOAD=1 \
./scripts/run.sh
```

Bu izin açıkken `faster-whisper`/Hugging Face model dosyalarına erişebilir. Kalıcı ve denetlenebilir çevrimdışı kullanım için üstteki kurulum-zamanı indirme yöntemini kullanın ve `.env` içinde `KLIPFORGE_ALLOW_MODEL_DOWNLOAD=0` bırakın.

## İsteğe bağlı yerel semantik yeniden sıralama

Klip adayları önce açıklanabilir yerel heuristiklerle puanlanır. Ardından çakışmaları azaltılmış, transkripti bulunan en fazla 10 adaylık bir havuz oluşturulur. Makinenizde Ollama ve önceden indirilmiş bir model varsa semantik katman bu havuzu hook, akış ve değer açısından yeniden puanlar. Son aşamada minimum puan, çeşitlilik ve `clip_count` sınırı yeniden uygulanır. Böylece Ollama havuzdaki daha düşük heuristik sıralı bir adayı öne çıkarabilir; havuzun dışındaki bölümleri ise incelemez.

```dotenv
KLIPFORGE_OLLAMA_MODEL=qwen3:4b
KLIPFORGE_OLLAMA_URL=http://127.0.0.1:11434
```

Modeli bir kez hazırlamak için, ağ erişimine açık olduğunuz kurulum aşamasında:

```bash
ollama pull qwen3:4b
```

Ardından Ollama'nın yerel servisinin çalıştığından emin olup `./scripts/run.sh` başlatın. Backend güvenlik gereği yalnızca `127.0.0.1`, `localhost` veya `::1` adresli Ollama URL'lerini kabul eder; uzak bir sunucu adresi verilirse semantik katman devre dışı kalır. Ollama kapalıysa, model yüklü değilse veya yanıt geçersizse analiz başarısız olmaz ve heuristik sıralama korunur. Bu özellik kapalıyken Ollama gerekmez.

## Yapılandırma ve port

`scripts/setup.sh`, mevcut değilse `.env.example` dosyasından `.env` oluşturur. Varsayılanlar:

```dotenv
KLIPFORGE_HOST=127.0.0.1
KLIPFORGE_PORT=3210
KLIPFORGE_ALLOW_MODEL_DOWNLOAD=0
KLIPFORGE_OLLAMA_MODEL=
KLIPFORGE_OLLAMA_URL=http://127.0.0.1:11434
```

Portu tek çalıştırma için değiştirmek:

```bash
KLIPFORGE_PORT=4321 ./scripts/run.sh
```

Başka cihazlardan erişmek için `KLIPFORGE_HOST=0.0.0.0` ayarlanabilir; ancak uygulamada kullanıcı doğrulaması yoktur. Güvenilmeyen bir ağa veya doğrudan internete bu şekilde açmayın.

Diğer seçenekler `.env.example` içinde açıklanmıştır. Ortam değişkenleri `.env` değerlerinin üzerine yazılabilir.

## Manuel kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

# Temel çalışma
python -m pip install -r requirements.txt

# veya Whisper + OpenCV dahil
python -m pip install -r requirements-ai.txt

npm --prefix frontend install --no-audit --no-fund
npm --prefix frontend run build
cp .env.example .env
./scripts/run.sh
```

`run.sh` ağdan paket kurmaz. `frontend/dist/index.html` yoksa yalnızca mevcut `node_modules` ile yeniden build etmeyi dener.

## Klasör yapısı

```text
app/                 FastAPI API, analiz, puanlama ve render kodu
frontend/            React/Vite kaynakları
frontend/dist/       FastAPI tarafından sunulan derlenmiş arayüz
data/projects/       Kaynak videolar, proje JSON'ları ve klip çıktıları
models/              Yerel faster-whisper modelleri
BASLAT-WINDOWS.bat   Windows tek-tık kurulum ve başlatma
BASLAT.sh            Linux/macOS/WSL otomatik kurulum ve başlatma
scripts/start.ps1    Windows PowerShell başlatıcısı
scripts/setup.sh     Bağımlılık ve frontend kurulum betiği
scripts/run.sh       Tek porttan yerel çalıştırma betiği
requirements.txt     Temel Python bağımlılıkları
requirements-ai.txt  Whisper ve OpenCV dahil isteğe bağlı bağımlılıklar
```

`data/`, `models/`, `.venv/` ve `frontend/node_modules/` büyük olabilir. Bunları kaynak kod deposuna eklemeyin.

## Sağlık kontrolü

Uygulama çalışırken:

```bash
curl http://127.0.0.1:3210/api/health
```

Yanıt; FFmpeg, ffprobe, transkripsiyon modeli ve OpenCV durumunu gösterir. `status: degraded` görürseniz önce `ffmpeg` ve `ffprobe` kurulumunu kontrol edin.

## Sınırlar

- Virallik puanı yerel, açıklanabilir bir sıralama sinyalidir; izlenme veya etkileşim garantisi değildir.
- Canlı sosyal trend verisi kullanılmaz; trend puanı hesaplanmaz, toplam puana katılmaz ve arayüzde “bilinmiyor” kalır. Sosyal ağ yayınlama, takvim, ekip çalışma alanı ve bulut senkronizasyonu yoktur.
- Ollama semantik sıralaması yalnızca heuristiklerden oluşturulan, transkripti bulunan en fazla 10 adaylık havuzu işler; havuzun dışındaki bölümleri değerlendiremez.
- URL'den uzaktaki video çekme yerine dosya yükleme akışı kullanılır.
- İş kuyruğu aynı Python sürecindedir; uygulama tek kullanıcı/tek makine kullanımı için tasarlanmıştır.
- Uvicorn birden fazla process worker ile başlatılmamalıdır; arka plan işleri süreç içi tutulur.
- CPU tabanlı transkripsiyon ve render, uzun veya yüksek çözünürlüklü videolarda gerçek zamandan yavaş olabilir.
- OpenCV kadrajı dinamik konuşmacı takibi yapmaz; örnek karelerde bulunan en büyük yüzlerin medyan yatay konumunu tüm klipte sabit kullanır. OpenCV kurulmazsa merkez kırpmaya düşer.
- Editörde başlangıç/bitiş zamanını değiştirmek klibin mevcut analiz puanını yeniden hesaplamaz; yeni bir puan için projeyi yeniden analiz etmek gerekir.
- Varsayılan yükleme sınırı 8 GB, video süresi sınırı 6 saattir.
- Proje silme işlemi ilgili yerel proje klasörünü kalıcı olarak kaldırır.
- Uygulama hazır bir çok kullanıcılı güvenlik/kimlik doğrulama katmanı içermez.

## Bağlantı reddedildi hatası

Tarayıcıda `ERR_CONNECTION_REFUSED` görülmesi, `3210` portunda KlipForge sunucusunun çalışmadığı anlamına gelir. Windows'ta `BASLAT-WINDOWS.bat`, Linux/macOS/WSL'de `./BASLAT.sh` çalıştırın ve açılan terminali kapatmayın. Başlatıcı sunucunun sağlık kontrolü başarılı olmadan tarayıcıyı açmaz; bir bağımlılık eksikse hata mesajını aynı pencerede gösterir.

## Sorun giderme

**Arayüz yerine 503 JSON yanıtı geliyor**

```bash
npm --prefix frontend run build
./scripts/run.sh
```

**“ffmpeg/ffprobe bulunamadı”**

Her iki komutun da PATH üzerinde olduğundan emin olun:

```bash
ffmpeg -version
ffprobe -version
```

**Transkripsiyon kullanılamıyor**

- `requirements-ai.txt` bağımlılıklarını kurun.
- Model klasöründe `model.bin` bulunduğunu doğrulayın.
- `.env` içindeki `KLIPFORGE_MODELS_DIR` ve `KLIPFORGE_WHISPER_MODEL` yollarını kontrol edin.
- `/api/health` yanıtındaki `engine.transcription` alanına bakın.

**Port kullanımda**

```bash
KLIPFORGE_PORT=4321 ./scripts/run.sh
```

