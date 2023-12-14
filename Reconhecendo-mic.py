#!/usr/bin/python
import argparse
import sys
from argparse import RawTextHelpFormatter
from itertools import zip_longest as izip_longest

import numpy as np
from termcolor import colored

import libs.fingerprint as fingerprint
from libs.config import get_config
from libs.db_sqlite import SqliteDatabase, SQLITE_MAX_VARIABLE_NUMBER
from libs.reader_microphone import MicrophoneReader
from libs.visualiser_console import VisualiserConsole as visual_peak
from libs.visualiser_plot import VisualiserPlot as visual_plot

# from libs.db_mongo import MongoDatabase


def align_matches(matches):
    diff_counter = {}
    largest = 0
    largest_count = 0
    song_id = -1

    for tup in matches:
        sid, diff = tup

        if diff not in diff_counter:
            diff_counter[diff] = {}

        if sid not in diff_counter[diff]:
            diff_counter[diff][sid] = 0

        diff_counter[diff][sid] += 1

        if diff_counter[diff][sid] > largest_count:
            largest = diff
            largest_count = diff_counter[diff][sid]
            song_id = sid

    songM = db.get_song_by_id(song_id)

    nseconds = round(float(largest) / fingerprint.DEFAULT_FS *
                     fingerprint.DEFAULT_WINDOW_SIZE *
                     fingerprint.DEFAULT_OVERLAP_RATIO, 5)

    return {
        "SONG_ID": song_id,
        "SONG_NAME": songM[1],
        "CONFIDENCE": largest_count,
        "OFFSET": int(largest),
        "OFFSET_SECS": nseconds
    }


def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return (filter(None, values)
            for values in izip_longest(fillvalue=fillvalue, *args))


def find_matches(samples, Fs=fingerprint.DEFAULT_FS):
    hashes = fingerprint.fingerprint(samples, Fs=Fs)
    return return_matches(hashes)


def return_matches(hashes): #def que tem como parâmetro os hashes
#Esta linha inicializa um dicionário vazio
#chamado mapper. Este dicionário será usado para mapear os hashes
#para seus deslocamentos.
    mapper = {}
#Esse loop percorre a lista de hashes, que contém os hashes de impressão digital e seus deslocamentos.
# Para cada hash, o loop converte o hash em letras maiúsculas e o armazena no dicionário do mapeador junto com seu deslocamento.
    for hash, offset in hashes:
        mapper[hash.upper()] = offset
    values = mapper.keys()
#dividir os valores em listas
    for split_values in map(list, grouper(values, SQLITE_MAX_VARIABLE_NUMBER)):
        # @todo move to db related files
        #Este bloco de código constrói uma consulta SQL que seleciona o ID da música e o
        # deslocamento para cada hash no bloco atual. O espaço reservado %s é usado para
        # representar a lista de hashes.
        query = """
    SELECT upper(hash), song_fk, offset
    FROM fingerprints
    WHERE upper(hash) IN (%s)
  """
        query = query % ', '.join('?' * len(split_values))

        x = db.executeAll(query, split_values)
        matches_found = len(x)

        if matches_found > 0:
            msg = '   ** Encontrado %d correspondências de hashs (passos %d/%d)'
            print(colored(msg, 'green') % (
                matches_found,
                len(split_values),
                len(values)
            ))
        else:
            msg = '   ** não foram encontradas correspondências(passos %d/%d)'
            print(colored(msg, 'red') % (len(split_values), len(values)))
        #Este loop itera sobre o x
        #hash_code é o hash da impressão digital, sid é o ID da música e offset é o deslocamento do hash dentro do arquivo de áudio.
        for hash_code, sid, offset in x:

            # (sid, db_offset - song_sampled_offset)

            #ESSE  bloco (IF) de código verifica se o valor do deslocamento é uma sequência de bytes.
            # Se for, o código assume que o deslocamento foi gerado pelo módulo fingerprint.py e o processa.
            if isinstance(offset, bytes):
                # offset come from fingerprint.py and numpy extraction/processing
                #Esta linha converte a sequência de bytes de deslocamento em um único valor inteiro. A função np.frombuffer() é
                # usada para converter a sequência de bytes em um vetor NumPy, e a indexação [0] é usada para extrair
                #o primeiro elemento do vetor
                offset = np.frombuffer(offset, dtype=np.int)[0]
            #Esta linha produz uma tupla contendo o ID da música e o deslocamento do hash no arquivo de áudio, relativo
            # ao deslocamento do hash no banco de dados. A expressão mapper[hash_code] recupera o deslocamento do hash
            #do dicionário mapeador.
            yield sid, offset - mapper[hash_code]


if __name__ == '__main__':
    config = get_config()

    db = SqliteDatabase()

    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter)
    parser.add_argument('-s', '--seconds', nargs='?')
    args = parser.parse_args()

    if not args.seconds:
        parser.print_help()
        sys.exit(0)

    seconds = int(args.seconds)

    chunksize = 2 ** 12  # 4096
    channels = 2  # int(config['channels']) # 1=mono, 2=stereo

    record_forever = False
    visualise_console = bool(config['mic.visualise_console'])
    visualise_plot = bool(config['mic.visualise_plot'])

    reader = MicrophoneReader(None)

    reader.start_recording(seconds=seconds,
                           chunksize=chunksize,
                           channels=channels)

    msg = '** Começou a gravar ...'
    print(colored(msg, attrs=['dark']))

    while True:
        bufferSize = int(reader.rate / reader.chunksize * seconds)

        for i in range(0, bufferSize):
            nums = reader.process_recording()

            if visualise_console:
                msg = colored('   %05d', attrs=['dark']) + colored(' %s', 'green')
                print(msg % visual_peak.calc(nums))
            else:
                msg = '   processando %d of %d..' % (i, bufferSize)
                print(colored(msg, attrs=['dark']))

        if not record_forever:
            break

    if visualise_plot:
        data = reader.get_recorded_data()[0]
        visual_plot.show(data)

    reader.stop_recording()

    msg = ' * A gravação foi interrompida'
    print(colored(msg, attrs=['dark']))

    data = reader.get_recorded_data()

    msg = ' * Amostras %d gravadas'
    print(colored(msg, attrs=['dark']) % len(data[0]))

    # reader.save_recorded('test.wav')

    Fs = fingerprint.DEFAULT_FS
    channel_amount = len(data)

    result = set()
    matches = []

    for channeln, channel in enumerate(data):
        
        msg = '   fingerprinting channel %d/%d'
        print(colored(msg, attrs=['dark']) % (channeln + 1, channel_amount))

        matches.extend(find_matches(channel))

        msg = '   finalizei o canal %d/%d, obtive %d hashes'
        print(colored(msg, attrs=['dark']) % (channeln + 1,
                                              channel_amount, len(matches)))

    total_matches_found = len(matches)

    print('')

    if total_matches_found > 4:
        msg = '*** %d correspondências de hash totalmente encontradas***'
        print(colored(msg, 'green') % total_matches_found)

        song = align_matches(matches)

        msg = ' =>Música: %s (id=%d)\n'
        msg += '    offset (desvio): %d (%d secs)\n'
        msg += '    Confiança: %d'

        print(colored(msg, 'green') % (song['SONG_NAME'], song['SONG_ID'],
                                       song['OFFSET'], song['OFFSET_SECS'],
                                       song['CONFIDENCE']))
    else:
        msg = ' ** não foram encontradas correspondências **'
        print(colored(msg, 'red'))
