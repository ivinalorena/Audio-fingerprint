#!/usr/bin/python
import os

from termcolor import colored

import fingerprint as fingerprint
from libs.config import get_config
from libs.db_sqlite import SqliteDatabase
from libs.reader_file import FileReader

if __name__ == '__main__':
    config = get_config()

    db = SqliteDatabase()
    path = "mp3/"

    #For principal que analisa todos os arquivos do path selecionado terminados com .wav
    for filename in os.listdir(path):
        #if filename.endswith(".mp3"):
        if filename.endswith(".wav"):
            reader = FileReader(path + filename)
            #pega informações do arquivo de audio
            audio = reader.parse_audio()
            #para obter informações sobre uma música com base no hash do arquivo de áudio
            song = db.get_song_by_filehash(audio['file_hash'])
            #adiciona a musica no banco de dados e o hash do arquivo
            #o resultado é adicionado a um novo ID
            song_id = db.add_song(filename, audio['file_hash'])

            msg = ' * %s %s: %s' % (
                colored('id=%s', 'white', attrs=['dark']),  # ID
                colored('channels=%d', 'white', attrs=['dark']),  # CANAIS
                colored('%s', 'white', attrs=['bold'])  # NOME DO ARQUIVO
            )
            print(msg % (song_id, len(audio['channels']), filename))

            if song:
                hash_count = db.get_song_hashes_count(song_id)

                if hash_count > 0:
                    msg = '   Já existe (%d hashes), pulando ...' % hash_count
                    print(colored(msg, 'red'))

                    continue

            print(colored('   Nova música, analisando..', 'green'))

            hashes = set()
            channel_amount = len(audio['channels'])
    #essa linha "soma" sobre a lista de canais de áudio no dicionário de áudio. A função enumerate() é usada para rastrear
    # o índice do canal atual. O índice é armazenado na variável channeln, e o próprio canal é armazenado na variável channel.
            for channeln, channel in enumerate(audio['channels']):
                msg = '   Canal da impressão digital %d/%d'
                print(colored(msg, attrs=['dark']) % (channeln + 1, channel_amount))

                #Essas linhas identificam o canal de áudio atual e armazenam os hashes resultantes na variável channel_hashes.
                # A função fingerprint() é usada para realizar a impressão digital.
                # O parâmetro Fs é definido como a taxa de amostragem dos dados de áudio, que é armazenada na variável audio['Fs'].
                #Frequência de amostragem: fs = 1/T [Hz ou amostras/s]
                channel_hashes = fingerprint.fingerprint(channel, Fs=audio['Fs'],
                                                         plots=config['fingerprint.show_plots'])
                #a função set() é usada para converter a lista de hashes em um conjunto,
                # que remove quaisquer hashes duplicados.
                channel_hashes = set(channel_hashes)

                msg = '   canal finalizado %d/%d, obtive %d hashes'

                #Imprime a mensagem de log formatada, indicando que o canal foi concluído,
                # o número total de canais e a quantidade de hashes únicos obtidos para o canal.
                print(colored(msg, attrs=['dark']) % (channeln + 1, channel_amount, len(channel_hashes)))
                #Adiciona os hashes únicos do canal ao conjunto geral de hashes (hashes).
                # O operador |= é usado para realizar uma união de conjuntos.
                hashes |= channel_hashes

            msg = 'terminei a impressao digital, obtive %d hashes exclusivos'

            #Esta linha cria uma lista vazia chamada valores.
            # Esta lista será utilizada para armazenar os dados da impressão digital que
            # serão inseridos no banco de dados.
            values = []

            #"adiciona" sobre os elementos do conjunto hashes, que aparentemente contém tuplas
            # (hash, offset). Para cada tupla, adiciona uma nova tupla à lista values
            # contendo o song_id, o hash e o offset. Isso cria uma estrutura de dados que
            # será armazenada posteriormente no banco de dados.
            for hash, offset in hashes:
                values.append((song_id, hash, offset))

            #Cria uma mensagem de log indicando quantos hashes serão armazenados no banco de
            # dados. O número de hashes é determinado pelo comprimento da lista values
            msg = '   Guardando %d hashes no banco de dados' % len(values)
            print(colored(msg, 'green'))
            #Chama a função passa a lista values como argumento e insere ou atualiza
            #registros no banco de dados com as informações coletadas.
            db.store_fingerprints(values)

    print('fim')
