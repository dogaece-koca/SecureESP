import mne
import pandas as pd
import numpy as np
import os
import pyedflib


def preprocess_eeg_for_export(file_path):
    """
    CSV dosyasını okur ve MNE Raw objesine dönüştürür.
    """
    try:
        # Ayırıcıyı otomatik algıla (virgül veya tab)
        df = pd.read_csv(file_path, sep=None, engine='python')
        df.columns = df.columns.str.strip()

        # Meta verileri temizle
        meta_keywords = ['patient', 'time', 'label', 'epoch']
        cols_to_drop = [col for col in df.columns if col.lower() in meta_keywords]
        df_signals = df.drop(columns=cols_to_drop)

        # Sayısal veriye çevir ve kopyala (ValueError: read-only hatasını önlemek için)
        df_signals = df_signals.apply(pd.to_numeric, errors='coerce').dropna()
        data = df_signals.values.T.copy()

        ch_names = df_signals.columns.tolist()
        sfreq = 250  # BCICIV_2a standart frekansı

        info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types='eeg')
        raw = mne.io.RawArray(data, info)

        # Sinyal kalitesini artırmak için temel filtreleme
        raw.filter(l_freq=8, h_freq=30, verbose=False)
        return raw
    except Exception as e:
        print(f"Hata: {e}")
        return None


def export_to_edf(raw_obj, output_path):
    """
    MNE Raw objesini EDF formatında kaydeder.
    """
    if raw_obj is None:
        return

    n_channels = len(raw_obj.ch_names)
    data = raw_obj.get_data()

    channel_info = []
    for ch_name in raw_obj.ch_names:
        ch_dict = {
            'label': ch_name,
            'dimension': 'uV',
            'sample_frequency': raw_obj.info['sfreq'],
            'physical_max': 1000,
            'physical_min': -1000,
            'digital_max': 32767,
            'digital_min': -32768,
            'transducer': '',
            'prefilter': ''
        }
        channel_info.append(ch_dict)

    f = pyedflib.EdfWriter(output_path, n_channels, file_type=pyedflib.FILETYPE_EDFPLUS)
    f.setSignalHeaders(channel_info)
    f.writeSamples(data)
    f.close()
    print(f"\n✅ Başarıyla çevrildi: {output_path}")


if __name__ == "__main__":
    input_csv = r"C:\Users\doaec\AppData\Local\Packages\5319275A.WhatsAppDesktop_cv1g1gvanyjgm\LocalState\sessions\4BC966460DF9B1FFB98FC246EFA1E735C98DA07F\transfers\2026-16\Motor imagery\Motor imagery\BrainFlow-RAW_2026-04-17_14-52-12_0.csv"
    output_edf = r"C:\Users\doaec\AppData\Local\Packages\5319275A.WhatsAppDesktop_cv1g1gvanyjgm\LocalState\sessions\4BC966460DF9B1FFB98FC246EFA1E735C98DA07F\transfers\2026-16\Motor imagery\Motor imagery\BrainFlow-RAW_2026-04-17_14-52-12_0.edf"

    if os.path.exists(input_csv):
        print(f"Dosya işleniyor: {os.path.basename(input_csv)}")
        raw_data = preprocess_eeg_for_export(input_csv)

        if raw_data:
            export_to_edf(raw_data, output_edf)
    else:
        print("Hata: Kaynak CSV dosyası bulunamadı!")