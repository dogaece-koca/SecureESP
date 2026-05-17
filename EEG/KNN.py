import mne
import pandas as pd
import os
from sklearn.neighbors import KNeighborsClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report


def preprocess_eeg_data(file_path):
    df = pd.read_csv(file_path)

    labels = df['label'].values

    meta_keywords = ['patient', 'time', 'label', 'epoch']
    cols_to_drop = [col for col in df.columns if col.lower() in meta_keywords]
    df_signals = df.drop(columns=cols_to_drop)

    data = df_signals.values.T
    ch_names = df_signals.columns.tolist()
    sfreq = 250

    info = mne.create_info(ch_names=ch_names, sfreq=sfreq, ch_types='eeg')
    raw = mne.io.RawArray(data, info)

    raw.filter(l_freq=8, h_freq=30, verbose=False)
    raw.resample(sfreq=128, verbose=False)
    raw.set_eeg_reference(ref_channels='average', verbose=False)

    return raw, labels


def get_features(raw_obj):
    events = mne.make_fixed_length_events(raw_obj, duration=4.0)
    epochs = mne.Epochs(raw_obj, events, tmin=-0.5, tmax=4.0, baseline=None, preload=True, verbose=False)

    psds = epochs.compute_psd(fmin=8, fmax=30).get_data()
    X = psds.mean(axis=-1)
    return X


if __name__ == "__main__":
    sample_file = r"C:\Users\doaec\PycharmProjects\ESPSecure\EEG\data\BCICIV_2a_all_patients.csv"

    if os.path.exists(sample_file):
        processed_raw, raw_labels = preprocess_eeg_data(sample_file)

        X = get_features(processed_raw)
        y = raw_labels[:X.shape[0]]

        print(f"Model eğitiliyor... Veri boyutu: {X.shape}")
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        knn = KNeighborsClassifier(n_neighbors=3, metric='cosine')
        knn.fit(X_train, y_train)

        y_pred = knn.predict(X_test)
        print("\n" + "=" * 30)
        print(f"kNN Başarı Oranı: %{accuracy_score(y_test, y_pred) * 100:.2f}")
        print("=" * 30)
        print(classification_report(y_test, y_pred))
    else:
        print("Hata: Dosya bulunamadı!")