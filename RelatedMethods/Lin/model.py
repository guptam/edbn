"""
    Implementation of MM-Pred: A Deep Predictive Model for Multi-attribute Event Sequence [Lin, Wen and Wang]

    Author: Stephen Pauwels
"""

import multiprocessing as mp
import os
from functools import partial

import jellyfish as jf
import keras.utils as ku
import numpy as np
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.layers import Input, Embedding, Dropout, Concatenate, LSTM, Dense, BatchNormalization
from keras.models import Model, load_model
from keras.optimizers import Nadam

from RelatedMethods.Lin.Modulator import Modulator


def create_model_cudnn(vec, vocab_act_size, vocab_role_size, output_folder):
    # Create embeddings + Concat
    act_input = Input(shape = (vec['prefixes']['x_ac_inp'].shape[1],), name="act_input")
    role_input = Input(shape = (vec['prefixes']['x_rl_inp'].shape[1],), name="role_input")

    act_embedding = Embedding(vocab_act_size, 100, input_length=vec['prefixes']['x_ac_inp'].shape[1],)(act_input)
    act_dropout = Dropout(0.2)(act_embedding)
    act_e_lstm_1 = LSTM(32, return_sequences=True)(act_dropout)
    act_e_lstm_2 = LSTM(100, return_sequences=True)(act_e_lstm_1)


    role_embedding = Embedding(vocab_role_size, 100, input_length=vec['prefixes']['x_rl_inp'].shape[1],)(role_input)
    role_dropout = Dropout(0.2)(role_embedding)
    role_e_lstm_1 = LSTM(32, return_sequences=True)(role_dropout)
    role_e_lstm_2 = LSTM(100, return_sequences=True)(role_e_lstm_1)

    concat1 = Concatenate(axis=1)([act_e_lstm_2, role_e_lstm_2])
    normal = BatchNormalization()(concat1)

    act_modulator = Modulator(attr_idx=0, num_attrs=1)(normal)
    role_modulator = Modulator(attr_idx=1, num_attrs=1)(normal)

    # Use LSTM to decode events
    act_d_lstm_1 = LSTM(100, return_sequences=True)(act_modulator)
    act_d_lstm_2 = LSTM(32, return_sequences=False)(act_d_lstm_1)

    role_d_lstm_1 = LSTM(100, return_sequences=True)(role_modulator)
    role_d_lstm_2 = LSTM(32, return_sequences=False)(role_d_lstm_1)

    act_output = Dense(vocab_act_size, name="act_output", activation='softmax')(act_d_lstm_2)
    role_output = Dense(vocab_role_size, name="role_output", activation="softmax")(role_d_lstm_2)

    model = Model(inputs=[act_input, role_input], outputs=[act_output, role_output])

    opt = Nadam(lr=0.002, beta_1=0.9, beta_2=0.999,
                epsilon=1e-08, schedule_decay=0.004, clipvalue=3)
    model.compile(loss={'act_output': 'categorical_crossentropy', 'role_output': 'categorical_crossentropy'}, optimizer=opt)

    model.summary()

    output_file_path = os.path.join(output_folder, 'model_rd_{epoch:03d}-{val_loss:.2f}.h5')

    # Saving
    model_checkpoint = ModelCheckpoint(output_file_path,
                                       monitor='val_loss',
                                       verbose=1,
                                       save_best_only=True,
                                       save_weights_only=False,
                                       mode='auto')

    early_stopping = EarlyStopping(monitor='val_loss', patience=42)

    model.fit({'act_input':vec['prefixes']['x_ac_inp'],
               'role_input':vec['prefixes']['x_rl_inp']},
              {'act_output':vec['next_evt']['y_ac_inp'],
               'role_output':vec['next_evt']['y_rl_inp']},
              validation_split=0.2,
              verbose=2,
              batch_size=5,
              callbacks=[early_stopping, model_checkpoint],
              epochs=200)

def create_model(log, output_folder, epochs, early_stop):
    vec = vectorization(log)
    vocab_act_size = len(log.values["event"]) + 1
    vocab_role_size = len(log.values["role"]) + 1

    # Create embeddings + Concat
    act_input = Input(shape=(vec['prefixes']['x_ac_inp'].shape[1],), name="act_input")
    role_input = Input(shape=(vec['prefixes']['x_rl_inp'].shape[1],), name="role_input")

    act_embedding = Embedding(vocab_act_size, 100, input_length=vec['prefixes']['x_ac_inp'].shape[1],)(act_input)
    act_dropout = Dropout(0.2)(act_embedding)
    act_e_lstm_1 = LSTM(32, return_sequences=True)(act_dropout)
    act_e_lstm_2 = LSTM(100, return_sequences=True)(act_e_lstm_1)


    role_embedding = Embedding(vocab_role_size, 100, input_length=vec['prefixes']['x_rl_inp'].shape[1],)(role_input)
    role_dropout = Dropout(0.2)(role_embedding)
    role_e_lstm_1 = LSTM(32, return_sequences=True)(role_dropout)
    role_e_lstm_2 = LSTM(100, return_sequences=True)(role_e_lstm_1)

    concat1 = Concatenate(axis=1)([act_e_lstm_2, role_e_lstm_2])
    normal = BatchNormalization()(concat1)

    act_modulator = Modulator(attr_idx=0, num_attrs=1, time=log.k)(normal)
    role_modulator = Modulator(attr_idx=1, num_attrs=1, time=log.k)(normal)

    # Use LSTM to decode events
    act_d_lstm_1 = LSTM(100, return_sequences=True)(act_modulator)
    act_d_lstm_2 = LSTM(32, return_sequences=False)(act_d_lstm_1)

    role_d_lstm_1 = LSTM(100, return_sequences=True)(role_modulator)
    role_d_lstm_2 = LSTM(32, return_sequences=False)(role_d_lstm_1)

    act_output = Dense(vocab_act_size, name="act_output", activation='softmax')(act_d_lstm_2)
    role_output = Dense(vocab_role_size, name="role_output", activation="softmax")(role_d_lstm_2)

    model = Model(inputs=[act_input, role_input], outputs=[act_output, role_output])

    opt = Nadam(lr=0.002, beta_1=0.9, beta_2=0.999,
                epsilon=1e-08, schedule_decay=0.004, clipvalue=3)
    model.compile(loss={'act_output': 'categorical_crossentropy', 'role_output': 'categorical_crossentropy'}, optimizer=opt)

    model.summary()

    output_file_path = os.path.join(output_folder, 'model_{epoch:03d}-{val_loss:.2f}.h5')

    # Saving
    model_checkpoint = ModelCheckpoint(output_file_path,
                                       monitor='val_loss',
                                       verbose=1,
                                       save_best_only=True,
                                       save_weights_only=False,
                                       mode='auto')

    early_stopping = EarlyStopping(monitor='val_loss', patience=early_stop)

    model.fit({'act_input':vec['prefixes']['x_ac_inp'],
               'role_input':vec['prefixes']['x_rl_inp']},
              {'act_output':vec['next_evt']['y_ac_inp'],
               'role_output':vec['next_evt']['y_rl_inp']},
              validation_split=0.2,
              verbose=2,
              batch_size=5,
              callbacks=[early_stopping, model_checkpoint],
              epochs=epochs)
    return model


def predict_next(log, model):
    prefixes = create_pref_next(log)
    prefixes = _predict_next(model, prefixes)

    accuracy = (np.sum([x['ac_true'] for x in prefixes]) / len(prefixes))

    print("Accuracy:", accuracy)
    return accuracy


def predict_suffix(model_file, df_test, end):
    model = load_model(os.path.join(model_file), custom_objects={'Modulator':Modulator})

    prefixes = create_pref_suff(df_test, end)
    prefixes = _predict_suffix(model, prefixes, 100, end)
    prefixes = dl_measure(prefixes)

    average_dl = (np.sum([x['suffix_dl'] for x in prefixes]) / len(prefixes))

    print("Average DL:", average_dl)
    return average_dl


def vectorization(log):
    """Example function with types documented in the docstring.
    Args:
        log_df (dataframe): event log data.
        ac_index (dict): index of activities.
        rl_index (dict): index of roles.
    Returns:
        dict: Dictionary that contains all the LSTM inputs.
    """
    print("Start Vectorization")

    vec = {'prefixes': dict(), 'next_evt': dict()}

    train_cases = log.get_cases()
    part_vect_map = partial(vect_map, prefix_size=log.k)
    with mp.Pool(mp.cpu_count()) as p:
        result = np.array(p.map(part_vect_map, train_cases))

    vec['prefixes']['x_ac_inp'] = np.concatenate(result[:, 0])
    vec['prefixes']['x_rl_inp'] = np.concatenate(result[:, 1])
    vec['next_evt']['y_ac_inp'] = np.concatenate(result[:, 2])
    vec['next_evt']['y_rl_inp'] = np.concatenate(result[:, 3])

    vec['next_evt']['y_ac_inp'] = ku.to_categorical(vec['next_evt']['y_ac_inp'], num_classes=len(log.values["event"])+1)
    vec['next_evt']['y_rl_inp'] = ku.to_categorical(vec['next_evt']['y_rl_inp'], num_classes=len(log.values["role"])+1)
    return vec


def map_case(x, log_df, case_attr):
    return log_df[log_df[case_attr] == x]


def vect_map(case, prefix_size):
    case_df = case[1]

    x_ac_inps = []
    x_rl_inps = []
    y_ac_inps = []
    y_rl_inps = []
    for row in case_df.iterrows():
        row = row[1]
        x_ac_inp = []
        x_rl_inp = []
        for i in range(prefix_size - 1, 0, -1):
            x_ac_inp.append(row["event_Prev%i" % i])
            x_rl_inp.append(row["role_Prev%i" % i])
        x_ac_inp.append(row["event_Prev0"])
        x_rl_inp.append(row["role_Prev0"])

        x_ac_inps.append(x_ac_inp)
        x_rl_inps.append(x_rl_inp)
        y_ac_inps.append(row["event"])
        y_rl_inps.append(row["role"])
    return [np.array(x_ac_inps), np.array(x_rl_inps), np.array(y_ac_inps), np.array(y_rl_inps)]


def create_pref_next(log):
    """Extraction of prefixes and expected suffixes from event log.
    Args:
        df_test (dataframe): testing dataframe in pandas format.
        case_attr: name of attribute containing case ID
        activity_attr: name of attribute containing the activity
    Returns:
        list: list of prefixes and expected sufixes.
    """
    prefixes = []
    cases = log.get_cases()
    for case in cases:
        trace = case[1]

        for row in trace.iterrows():
            row = row[1]
            ac_pref = []
            rl_pref = []
            t_pref = []
            for i in range(log.k - 1, -1, -1):
                ac_pref.append(row["event_Prev%i" % i])
                rl_pref.append(row["role_Prev%i" % i])
                t_pref.append(0)
            prefixes.append(dict(ac_pref=ac_pref,
                                 ac_next=row["event"],
                                 rl_pref=rl_pref,
                                 rl_next=row["role"],
                                 t_pref=t_pref))
    return prefixes

def create_pref_suff(df_test, end):
    """Extraction of prefixes and expected suffixes from event log.
    Args:
        df_test (dataframe): testing dataframe in pandas format.
        end: value representing the END token
    Returns:
        list: list of prefixes and expected sufixes.
    """
    prefixes = list()
    cases = df_test.case.unique()
    for case in cases:
        trace = df_test[df_test.case == case].to_dict('records')
        ac_pref = list()
        rl_pref = list()
        for i in range(0, len(trace)-1):
            ac_pref.append(trace[i]['event'])
            rl_pref.append(trace[i]['role'])
            prefixes.append(dict(ac_pref=ac_pref.copy(),
                                 suff=[x['event'] for x in trace[i + 1:]],
                                 rl_pref=rl_pref.copy(),
                                 rl_suff=[x['role'] for x in trace[i + 1:]],
                                 pref_size=i + 1))
    for x in prefixes:
        x['suff'].append(end)
        # x['rl_suff'].append(rl_index['end'])
    return prefixes

def _predict_next(model, prefixes):
    """Generate business process suffixes using a keras trained model.
    Args:
        model (keras model): keras trained model.
        prefixes (list): list of prefixes.
    """
    # Generation of predictions
    for prefix in prefixes:

        # Activities and roles input shape(1,5)
        x_ac_ngram = [prefix['ac_pref']]
        x_rl_ngram = [prefix['rl_pref']]

        predictions = model.predict([x_ac_ngram, x_rl_ngram])

        pos = np.argmax(predictions[0][0])

        # Activities accuracy evaluation
        if pos == prefix['ac_next']:
            prefix['ac_true'] = 1
        else:
            prefix['ac_true'] = 0

    return prefixes


def _predict_suffix(model, prefixes, max_trace_size, end):
    """Generate business process suffixes using a keras trained model.
    Args:
        model (keras model): keras trained model.
        prefixes (list): list of prefixes.
        max_trace_size: maximum length of a trace in the log
        end: value representing the END token
    """
    # Generation of predictions
    for prefix in prefixes:
        # Activities and roles input shape(1,5)
        x_ac_ngram = np.append(
            np.zeros(5),
            np.array(prefix['ac_pref']),
            axis=0)[-5:].reshape((1, 5))

        x_rl_ngram = np.append(
            np.zeros(5),
            np.array(prefix['rl_pref']),
            axis=0)[-5:].reshape((1, 5))

        ac_suf, rl_suf = list(), list()
        for _ in range(1, max_trace_size):
            predictions = model.predict([x_ac_ngram, x_rl_ngram])
            pos = np.argmax(predictions[0][0])
            pos1 = np.argmax(predictions[1][0])
            # Activities accuracy evaluation
            x_ac_ngram = np.append(x_ac_ngram, [[pos]], axis=1)
            x_ac_ngram = np.delete(x_ac_ngram, 0, 1)

            x_rl_ngram = np.append(x_rl_ngram, [[pos1]], axis=1)
            x_rl_ngram = np.delete(x_rl_ngram, 0, 1)

            # Stop if the next prediction is the end of the trace
            # otherwise until the defined max_size
            ac_suf.append(pos)
            rl_suf.append(pos1)

            if pos == end:
                break

        prefix['suff_pred'] = ac_suf
        prefix['rl_suff_pred'] = rl_suf
    return prefixes


def dl_measure(prefixes):
    """Demerau-Levinstain distance measurement.
    Args:
        prefixes (list): list with predicted and expected suffixes.
    Returns:
        list: list with measures added.
    """
    for prefix in prefixes:
        suff_log = str([x for x in prefix['suff']])
        suff_pred = str([x for x in prefix['suff_pred']])

        length = np.max([len(suff_log), len(suff_pred)])
        sim = jf.damerau_levenshtein_distance(suff_log,
                                              suff_pred)
        sim = (1 - (sim / length))
        prefix['suffix_dl'] = sim
    return prefixes

def train(logfile, train_log, model_folder):
    create_model(vectorization(train_log.data, train_log.trace, "event", num_classes=len(logfile.values[logfile.activity]) + 1), len(logfile.values[logfile.activity]) + 1, len(logfile.values["role"]) + 1, model_folder)

