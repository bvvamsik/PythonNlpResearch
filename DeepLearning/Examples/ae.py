import theano
import theano.tensor as T
from layer import AEHiddenLayer
import numpy

class Nonlinearity:
    RELU = "rectifier"
    TANH = "tanh"
    SIGMOID = "sigmoid"

class CostType:
    MeanSquared = "MeanSquaredCost"
    CrossEntropy = "CrossEntropy"

class Autoencoder(object):
    def __init__(self,
            input,
            nvis,
            nhid,
            rnd=None,
            bhid=None,
            cost_type=CostType.MeanSquared,
            momentum=1,
            L2_reg=-1,
            L1_reg=-1,
            sparse_initialize=True,
            nonlinearity=Nonlinearity.TANH,
            bvis=None,
            tied_weights=True):

        self.input = input
        self.nvis = nvis
        self.nhid = nhid
        self.bhid = bhid
        self.bvis = bvis
        self.momentum = momentum
        self.nonlinearity = nonlinearity
        self.tied_weights = tied_weights
        self.gparams = None

        if cost_type == CostType.MeanSquared:
            self.cost_type = CostType.MeanSquared
        elif cost_type == CostType.CrossEntropy:
            self.cost_type = CostType.CrossEntropy

        if self.input is None:
            self.input = T.distance_matrix('x')

        if rnd is None:
            self.rnd = numpy.random.RandomState(1231)
        else:
            self.rnd = rnd

        self.hidden = AEHiddenLayer(input,
                nvis,
                nhid,
                activation=None,
                tied_weights=tied_weights,
                sparse_initialize=sparse_initialize,
                rng=rnd)
        self.params = self.hidden.params

        self.L1_reg = L1_reg
        self.L2_reg = L2_reg

        self.sparse_initialize = sparse_initialize

        self.L1 = 0
        self.L2 = 0

        if L1_reg != -1:
            self.L1 += abs(self.hidden.W).sum()

        if L2_reg != -1:
            self.L2 += (self.hidden.W**2).sum()

        if input is not None:
            self.x = input
        else:
            self.x = T.dmatrix('x_input')

    def nonlinearity_fn(self, d_in=None, recons=False):
        if self.nonlinearity == Nonlinearity.SIGMOID:
            return T.nnet.sigmoid(d_in)
        elif self.nonlinearity == Nonlinearity.RELU and not recons:
            return T.maximum(d_in, 0)
        elif self.nonlinearity == Nonlinearity.RELU and recons:
            return T.nnet.softplus(d_in)
        elif self.nonlinearity == Nonlinearity.TANH:
            return T.tanh(d_in)

    def encode(self, x_in=None):
        if x_in is None:
            x_in = self.x
        return self.nonlinearity_fn(T.dot(x_in, self.hidden.W) + self.hidden.b)

    def encode_linear(self, x_in=None):
        if x_in is None:
            x_in = self.x
        lin_output = T.dot(x_in, self.hidden.W) + self.hidden.b
        return self.nonlinearity_fn(lin_output), lin_output

    def decode(self, h):
        return self.nonlinearity_fn(T.dot(h, self.hidden.W_prime) + self.hidden.b_prime)

    def get_rec_cost(self, x_rec):
        """
        Returns the reconstruction cost.
        """
        if self.cost_type == CostType.MeanSquared:
            return T.mean(((self.x - x_rec)**2).sum(axis=1))
        elif self.cost_type == CostType.CrossEntropy:
            return T.mean((T.nnet.binary_crossentropy(x_rec, self.x)).sum(axis=1))

    def kl_divergence(self, p, p_hat):
        return p * T.log(p / p_hat) + (1 - p) * T.log((1 - p) / (1 - p_hat))

    def sparsity_penalty(self, h, sparsity_level=0.05, sparse_reg=1e-3, batch_size=-1):
        if batch_size == -1 or batch_size == 0:
            raise Exception("Invalid batch_size!")
        sparsity_level = T.extra_ops.repeat(sparsity_level, self.nhid)
        sparsity_penalty = 0
        avg_act = h.mean(axis=0)
        kl_div = self.kl_divergence(sparsity_level, avg_act)
        sparsity_penalty = sparse_reg * kl_div.sum()
        # Implement KL divergence here.
        return sparsity_penalty

    def get_sgd_updates(self, learning_rate, lr_scaler=1.0, batch_size=-1, sparsity_level=-1, sparse_reg=-1, x_in=None):

        h = self.encode(x_in)
        x_rec = self.decode(h)
        cost = self.get_rec_cost(x_rec)

        if self.L1_reg != -1 and self.L1_reg is not None:
            cost += self.L1_reg * self.L1

        if self.L2_reg != -1 and self.L2_reg is not None:
            cost += self.L2_reg * self.L2

        if sparsity_level != -1 and sparse_reg != -1:
            sparsity_penal = self.sparsity_penalty(h, sparsity_level, sparse_reg, batch_size)
            cost += sparsity_penal

        self.gparams = T.grad(cost, self.params)
        updates = {}
        for param, gparam in zip(self.params, self.gparams):
            updates[param] = self.momentum * param - lr_scaler * learning_rate * gparam
        return (cost, updates)

    def fit(self,
            data=None,
            learning_rate=0.1,
            batch_size=100,
            n_epochs=20,
            lr_scaler=0.998,
            weights_file="out/ae_weights_mnist.npy"):
        """
        Fit the data to the autoencoder model. Basically this performs
        the learning.
        """
        if data is None:
            raise Exception("Data can't be empty.")

        index = T.lscalar('index')
        data_shared = theano.shared(numpy.asarray(data.tolist(), dtype=theano.config.floatX))
        n_batches = data.shape[0] / batch_size
        (cost, updates) = self.get_sgd_updates(learning_rate, lr_scaler, batch_size)
        train_ae = theano.function([index],
                                   cost,
                                   updates=updates,
                                   givens={
                                       self.x: data_shared[index * batch_size: (index + 1) * batch_size]
                                       }
                                   )

        print "Started the training."
        ae_costs = []

        for epoch in xrange(n_epochs):
            print "Training at epoch %d" % epoch
            for batch_index in xrange(n_batches):
                ae_costs.append(train_ae(batch_index))
            print "Training at epoch %d, %f" % (epoch, numpy.mean(ae_costs))

        print "Saving files..."
        numpy.save(weights_file, self.params[0].get_value())
        return ae_costs