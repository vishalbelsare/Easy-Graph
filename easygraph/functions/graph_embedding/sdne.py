import time

import numpy as np
import scipy.sparse as sp

from easygraph.utils import *


def get_relation_of_index_and_node(graph):
    node2idx = {}
    idx2node = []
    node_size = 0
    for node in graph.nodes:
        node2idx[node] = node_size
        idx2node.append(node)
        node_size += 1
    return idx2node, node2idx


def l_2nd(beta):
    try:
        pass
    except ImportWarning:
        print("tensorflow not found, please install")
    from tensorflow.python.keras import backend as K

    def loss_2nd(y_true, y_pred):
        y_true_numpy = y_true.numpy()
        b_ = np.ones_like(y_true.numpy())
        b_[y_true_numpy != 0] = beta
        x = K.square((y_true - y_pred) * b_)
        t = K.sum(
            x,
            axis=-1,
        )
        return K.mean(t)

    return loss_2nd


def l_1st(alpha):
    try:
        import tensorflow as tf
    except ImportWarning:
        print("tensorflow not found, please install")
    from tensorflow.python.keras import backend as K

    def loss_1st(y_true, y_pred):
        L = y_true
        Y = y_pred
        batch_size = tf.cast(K.shape(L)[0], dtype=tf.float32)
        return (
            alpha
            * 2
            * tf.linalg.trace(tf.matmul(tf.matmul(Y, L, transpose_a=True), Y))
            / batch_size
        )

    return loss_1st


def create_model(node_size, hidden_size=[256, 128], l1=1e-5, l2=1e-4):
    try:
        pass
    except ImportWarning:
        print("tensorflow not found, please install")
    from tensorflow.python.keras.layers import Dense
    from tensorflow.python.keras.layers import Input
    from tensorflow.python.keras.models import Model
    from tensorflow.python.keras.regularizers import l1_l2

    A = Input(shape=(node_size,))
    L = Input(shape=(None,))
    fc = A
    for i in range(len(hidden_size)):
        if i == len(hidden_size) - 1:
            fc = Dense(
                hidden_size[i],
                activation="relu",
                kernel_regularizer=l1_l2(l1, l2),
                name="1st",
            )(fc)
        else:
            fc = Dense(
                hidden_size[i], activation="relu", kernel_regularizer=l1_l2(l1, l2)
            )(fc)
    Y = fc
    for i in reversed(range(len(hidden_size) - 1)):
        fc = Dense(hidden_size[i], activation="relu", kernel_regularizer=l1_l2(l1, l2))(
            fc
        )

    A_ = Dense(node_size, "relu", name="2nd")(fc)
    model = Model(inputs=[A, L], outputs=[A_, Y])
    emb = Model(inputs=A, outputs=Y)
    return model, emb


class SDNE:
    @not_implemented_for("multigraph")
    def __init__(
        self,
        graph,
        hidden_size=[32, 16],
        alpha=1e-6,
        beta=5.0,
        nu1=1e-5,
        nu2=1e-4,
    ):
        """Graph embedding via SDNE.

        Parameters
        ----------
        graph : easygraph.Graph, easygraph.DiGraph

        hidden_size : list of two elements, optional (default : [32, 16])
            The hidden size.

        alpla : float, optional (default : 1e-6)
            The alpha value in [1]_.

        beta : float, optional (default : 5.)
            The beta value in [1]_.

        nu1 : float, optional (default : 1e-5)
            The nu1 value in [1]_.

        nu2 : float, optional (default : 1e-4)
            The nu2 value in [1]_.

        Examples
        --------
        >>> model = SDNE(G,
            ...          hidden_size=[256, 128]) # The hidden size in SDNE.
        >>> model.train(batch_size=3000, epochs=40, verbose=2)
        >>> embeddings = model.get_embeddings() # Returns the graph embedding results.

        References
        ----------
        .. [1] Wang D, Cui P, Zhu W. Structural deep network embedding[C]
           //Proceedings of the 22nd ACM SIGKDD international conference on
           Knowledge Discovery and Data mining. 2016: 1225-1234.

        """
        self.graph = graph
        self.idx2node, self.node2idx = get_relation_of_index_and_node(self.graph)

        self.node_size = self.graph.number_of_nodes()
        self.hidden_size = hidden_size
        self.alpha = alpha
        self.beta = beta
        self.nu1 = nu1
        self.nu2 = nu2

        self.A, self.L = self._create_A_L(
            self.graph, self.node2idx
        )  # Adj Matrix,L Matrix
        self.reset_model()
        self.inputs = [self.A, self.L]
        self._embeddings = {}

    def reset_model(self, opt="adam"):
        self.model, self.emb_model = create_model(
            self.node_size, hidden_size=self.hidden_size, l1=self.nu1, l2=self.nu2
        )
        self.model.compile(
            optimizer=opt, loss=[l_2nd(self.beta), l_1st(self.alpha)], run_eagerly=True
        )
        self.get_embeddings()

    def train(self, batch_size=1024, epochs=2, initial_epoch=0, verbose=1):
        """Train SDNE model.

        Parameters
        ----------
        batch_size : int, optional (default : 1024)

        epochs : int, optional (default : 2)

        initial_epoch : int, optional (default : 0)

        verbose : int, optional (default : 1)

        """
        try:
            pass
        except ImportWarning:
            print("tensorflow not found, please install")
        from tensorflow.python.keras.callbacks import History

        if batch_size >= self.node_size:
            if batch_size > self.node_size:
                print(
                    "batch_size({0}) > node_size({1}),set batch_size = {1}".format(
                        batch_size, self.node_size
                    )
                )
                batch_size = self.node_size
            return self.model.fit(
                [self.A.todense(), self.L.todense()],
                [self.A.todense(), self.L.todense()],
                batch_size=batch_size,
                epochs=epochs,
                initial_epoch=initial_epoch,
                verbose=verbose,
                shuffle=False,
            )
        else:
            steps_per_epoch = (self.node_size - 1) // batch_size + 1
            hist = History()
            hist.on_train_begin()
            logs = {}
            for epoch in range(initial_epoch, epochs):
                start_time = time.time()
                losses = np.zeros(3)
                for i in range(steps_per_epoch):
                    index = np.arange(
                        i * batch_size, min((i + 1) * batch_size, self.node_size)
                    )
                    A_train = self.A[index, :].todense()
                    L_mat_train = self.L[index][:, index].todense()
                    inp = [A_train, L_mat_train]
                    batch_losses = self.model.train_on_batch(inp, inp)
                    losses += batch_losses
                losses = losses / steps_per_epoch

                logs["loss"] = losses[0]
                logs["2nd_loss"] = losses[1]
                logs["1st_loss"] = losses[2]
                epoch_time = int(time.time() - start_time)
                # TODO: Fixed the bug derivated by the following code in TF2:
                # hist.on_epoch_end(epoch, logs)
                if verbose > 0:
                    print(f"Epoch {epoch + 1}/{epochs}")
                    print(
                        "{}s - loss: {: .4f} - 2nd_loss: {: .4f} - 1st_loss: {: .4f}"
                        .format(epoch_time, losses[0], losses[1], losses[2])
                    )
            return hist

    def evaluate(
        self,
    ):
        return self.model.evaluate(
            x=self.inputs, y=self.inputs, batch_size=self.node_size
        )

    def get_embeddings(self):
        """Returns the embedding of each node.

        Returns
        -------
        get_embeddings : dict
            The graph embedding result of each node.

        """
        self._embeddings = {}
        embeddings = self.emb_model.predict(self.A.todense(), batch_size=self.node_size)
        look_back = self.idx2node
        for i, embedding in enumerate(embeddings):
            self._embeddings[look_back[i]] = embedding

        return self._embeddings

    def _create_A_L(self, graph, node2idx):
        node_size = graph.number_of_nodes()
        A_data = []
        A_row_index = []
        A_col_index = []

        for edge in graph.edges:
            v1, v2 = edge[0], edge[1]
            edge_weight = graph[v1][v2].get("weight", 1)

            A_data.append(edge_weight)
            A_row_index.append(node2idx[v1])
            A_col_index.append(node2idx[v2])

        A = sp.csr_matrix(
            (A_data, (A_row_index, A_col_index)), shape=(node_size, node_size)
        )
        A_ = sp.csr_matrix(
            (A_data + A_data, (A_row_index + A_col_index, A_col_index + A_row_index)),
            shape=(node_size, node_size),
        )

        D = sp.diags(A_.sum(axis=1).flatten().tolist()[0])
        L = D - A_
        return A, L
