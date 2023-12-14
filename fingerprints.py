import hashlib
import numpy as np
import matplotlib.mlab as mlab
import matplotlib.pyplot as plt

from termcolor import colored
from scipy.ndimage.filters import maximum_filter
from scipy.ndimage.morphology import (generate_binary_structure, iterate_structure,
                                      binary_erosion)
from operator import itemgetter

IDX_FREQ_I = 0
IDX_TIME_J = 1

# o range das frequências que detecta
DEFAULT_FS = 44100

# Size of the FFT window, affects frequency granularity
DEFAULT_WINDOW_SIZE = 4096

DEFAULT_OVERLAP_RATIO = 0.5


# Grau em que uma impressão digital pode ser emparelhada com seus vizinhos --
#quanto maior causará mais impressões digitais, mas potencialmente melhor precisão.
DEFAULT_FAN_VALUE = 20

# Amplitude mínima no espectrograma para ser considerado um pico.
# Isto pode ser aumentado para reduzir o número de impressões digitais, mas pode
# afeta a precisão.
DEFAULT_AMP_MIN = 10

# Número de células em torno de um pico de amplitude no espectrograma em ordem
# para Dejavu considerá-lo um pico espectral. Valores mais altos significam menos
# impressões digitais e correspondência mais rápida, mas podem afetar potencialmente a precisão.
PEAK_NEIGHBORHOOD_SIZE = 10

# Limites de quão próximas ou distantes as impressões digitais podem estar no tempo, em ordem
# para ser emparelhado como uma impressão digital. Se o seu máximo for muito baixo, valores mais altos de
# DEFAULT_FAN_VALUE pode não funcionar conforme o esperado.
MIN_HASH_TIME_DELTA = 0
MAX_HASH_TIME_DELTA = 200

# Se True, classificará os picos temporariamente para impressão digital;
# não classificar reduzirá o número de impressões digitais, mas potencialmente
# afeta o desempenho.
PEAK_SORT = True

# Número de bits a serem descartados na frente do hash SHA1 no
# cálculo de impressão digital. Quanto mais você joga fora, menos armazenamento, mas
# colisões e erros de classificação potencialmente maiores ao identificar músicas.
FINGERPRINT_REDUCTION = 15
#FINGERPRINT_REDUCTION = 20


def fingerprint(channel_samples, Fs=DEFAULT_FS,
                wsize=DEFAULT_WINDOW_SIZE,
                wratio=DEFAULT_OVERLAP_RATIO,
                fan_value=DEFAULT_FAN_VALUE,
                amp_min=DEFAULT_AMP_MIN,
                plots=False):


    # plot the angle spectrum of segments within the signal in a colormap
    arr2D = mlab.specgram(
        channel_samples,
        NFFT=wsize,
        Fs=Fs,
        window=mlab.window_hanning,
        noverlap=int(wsize * wratio))[0]

    # show spectrogram plot
    if plots:
        plt.plot(arr2D)
        plt.title('FFT')
        plt.show()

    #aplique a transformação de log, pois o specgram retorna uma matriz linear
    arr2D = 10 * np.log10(arr2D)

    #arr2D = 10 * np.log10(arr2D)
    arr2D[arr2D == -np.inf] = 0  #substitua infos por zeros

    #Encontra o "local_maxima"
    local_maxima = list(get_2D_peaks(arr2D, plot=plots, amp_min=amp_min))

    msg = '   local_maxima: %d de pares de frequência e tempo'
    print(colored(msg, attrs=['dark']) % len(local_maxima))

    # returna os hashes
    return generate_hashes(local_maxima, fan_value=fan_value)


def get_2D_peaks(arr2D, plot=True, amp_min=DEFAULT_AMP_MIN):
    # http://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.morphology.iterate_structure.html#scipy.ndimage.morphology.iterate_structure
    struct = generate_binary_structure(2, 1)
    neighborhood = iterate_structure(struct, PEAK_NEIGHBORHOOD_SIZE)

    # encontrar máximos locais usando o filtro "vizinhança"
    local_max = maximum_filter(arr2D, footprint=neighborhood) == arr2D
    background = (arr2D == 0)
    eroded_background = binary_erosion(background, structure=neighborhood,
                                       border_value=1)
    #Máscara booleana de arr2D com True nos picos
    detected_peaks = local_max ^ eroded_background

    #extrair picos
    amps = arr2D[detected_peaks]
    j, i = np.where(detected_peaks)

    #Filtrar os picos encontrados
    amps = amps.flatten()
    peaks = zip(i, j, amps)
    peaks_filtered = [x for x in peaks if x[2] > amp_min]  # freq, time, amp

    #obter índices de frequência e tempo
    frequency_idx = [x[1] for x in peaks_filtered]
    time_idx = [x[0] for x in peaks_filtered]

    # scatter of the peaks
    if plot:
        fig, ax = plt.subplots()
        ax.imshow(arr2D)
        ax.scatter(time_idx, frequency_idx)
        ax.set_xlabel('Time')
        ax.set_ylabel('Frequency')
        ax.set_title("Spectrogram")
        plt.gca().invert_yaxis()
        plt.show()

    return zip(frequency_idx, time_idx)



def generate_hashes(peaks, fan_value=DEFAULT_FAN_VALUE):
    if PEAK_SORT:
        peaks.sort(key=itemgetter(1))

    # Todos os picos
    for i in range(len(peaks)):
        for j in range(1, fan_value):
            if (i + j) < len(peaks):

                # pegue o valor de frequência de pico atual e próximo
                freq1 = peaks[i][IDX_FREQ_I]
                freq2 = peaks[i + j][IDX_FREQ_I]

                # pegue o deslocamento do tempo de pico atual e próximo
                t1 = peaks[i][IDX_TIME_J]
                t2 = peaks[i + j][IDX_TIME_J]

                #diferenças de compensações de tempo
                t_delta = t2 - t1

                #verificando se o delta está entre mínimo e máximo
                if MIN_HASH_TIME_DELTA <= t_delta <= MAX_HASH_TIME_DELTA:
                    hash_code = "%s|%s|%s" % (str(freq1), str(freq2), str(t_delta))
                    h = hashlib.sha1(hash_code.encode('utf-8'))
                    yield (h.hexdigest()[0:FINGERPRINT_REDUCTION], t1)
