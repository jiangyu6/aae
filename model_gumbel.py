from six.moves import xrange
#import better_exceptions
import tensorflow as tf
import numpy as np
from workspace.tfvqvae.ops import *
#from commons.ops import *

def _gumbel_mnist_arch(d):
    with tf.variable_scope('enc') as enc_param_scope :
        enc_spec = [
            Conv2d('conv2d_1',1,d//4,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            Conv2d('conv2d_2',d//4,d//2,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            Conv2d('conv2d_3',d//2,d,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
        ]
    with tf.variable_scope('dec') as dec_param_scope :
        dec_spec = [
            TransposedConv2d('tconv2d_1',d,d//2,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            TransposedConv2d('tconv2d_2',d//2,d//4,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            TransposedConv2d('tconv2d_3',d//4,1,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.sigmoid(t),
        ]
    return enc_spec,enc_param_scope,dec_spec,dec_param_scope
def _mnist_arch(d):
    with tf.variable_scope('enc') as enc_param_scope :
        enc_spec = [
            Conv2d('conv2d_1',1,d//4,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            Conv2d('conv2d_2',d//4,d//2,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            Conv2d('conv2d_3',d//2,d,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
        ]
    with tf.variable_scope('dec') as dec_param_scope :
        dec_spec = [
            TransposedConv2d('tconv2d_1',d,d//2,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            TransposedConv2d('tconv2d_2',d//2,d//4,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            TransposedConv2d('tconv2d_3',d//4,1,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.sigmoid(t),
        ]
    return enc_spec,enc_param_scope,dec_spec,dec_param_scope

def _cifar10_arch(d):
    def _residual(t,conv3,conv1):
        return conv1(tf.nn.relu(conv3(tf.nn.relu(t))))+t
    from functools import partial

    with tf.variable_scope('enc') as enc_param_scope :
        enc_spec = [
            Conv2d('conv2d_1',3,d,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            Conv2d('conv2d_2',d,d,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            partial(_residual,
                    conv3=Conv2d('res_1_3',d,d,3,3,1,1,data_format='NHWC'),
                    conv1=Conv2d('res_1_1',d,d,1,1,1,1,data_format='NHWC')),
            partial(_residual,
                    conv3=Conv2d('res_2_3',d,d,3,3,1,1,data_format='NHWC'),
                    conv1=Conv2d('res_2_1',d,d,1,1,1,1,data_format='NHWC')),
        ]
    with tf.variable_scope('dec') as dec_param_scope :
        dec_spec = [
            partial(_residual,
                    conv3=Conv2d('res_1_3',d,d,3,3,1,1,data_format='NHWC'),
                    conv1=Conv2d('res_1_1',d,d,1,1,1,1,data_format='NHWC')),
            partial(_residual,
                    conv3=Conv2d('res_2_3',d,d,3,3,1,1,data_format='NHWC'),
                    conv1=Conv2d('res_2_1',d,d,1,1,1,1,data_format='NHWC')),
            TransposedConv2d('tconv2d_1',d,d,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            TransposedConv2d('tconv2d_2',d,3,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.sigmoid(t),
        ]
    return enc_spec,enc_param_scope,dec_spec,dec_param_scope

def _imagenet_arch(d,num_residual=4):
    def _residual(t,conv3,conv1):
        return conv1(tf.nn.relu(conv3(tf.nn.relu(t))))+t
    from functools import partial

    with tf.variable_scope('enc') as enc_param_scope :
        enc_spec = [
            Conv2d('conv2d_1',3,d//2,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            Conv2d('conv2d_2',d//2,d,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
        ]
        enc_spec += [
            partial(_residual,
                    conv3=Conv2d('res_%d_3'%i,d,d,3,3,1,1,data_format='NHWC'),
                    conv1=Conv2d('res_%d_1'%i,d,d,1,1,1,1,data_format='NHWC'))
            for i in range(num_residual)
        ]
    with tf.variable_scope('dec') as dec_param_scope :
        dec_spec = [
            partial(_residual,
                    conv3=Conv2d('res_%d_3'%i,d,d,3,3,1,1,data_format='NHWC'),
                    conv1=Conv2d('res_%d_1'%i,d,d,1,1,1,1,data_format='NHWC'))
            for i in range(num_residual)
        ]
        dec_spec += [
            lambda t,**kwargs : tf.nn.relu(t),
            TransposedConv2d('tconv2d_1',d,d//2,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.relu(t),
            TransposedConv2d('tconv2d_2',d//2,3,data_format='NHWC'),
            lambda t,**kwargs : tf.nn.sigmoid(t),
        ]
    return enc_spec,enc_param_scope,dec_spec,dec_param_scope

class GumbelVAE():
    def __init__(self,tau,lr,global_step,beta,
                 x,K,D,
                 arch_fn,
                 param_scope,mode='train'):
                 #param_scope,is_training=False):
        with tf.variable_scope(param_scope):
            enc_spec,enc_param_scope,dec_spec,dec_param_scope = arch_fn(D)
            with tf.variable_scope('embed') :
                embeds = tf.get_variable('embed', [K,D],
                                        initializer=tf.truncated_normal_initializer(stddev=0.02))
                self.embeds = embeds

        with tf.variable_scope('forward') as forward_scope:
            # Encoder Pass
            _t = x
            for block in enc_spec :
                _t = block(_t)
            z_e = _t
            self.z_e = z_e # -> [batch,latent_h,latent_w,D]

            # replace vqvae middel area as gumbel softmax
            logits_y = z_e
            def sampling(logits_y):
                U = tf.random_uniform(tf.shape(logits_y), 0, 1)
                y = logits_y - tf.log(-tf.log(U + 1e-20) + 1e-20) # logits + gumbel noise
                y = tf.nn.softmax(y / tau)
                #y = tf.nn.softmax(tf.reshape(y, (-1, D, M)) / tau)
                #y = tf.reshape(y, (-1, D*))
                return y
            z = sampling(logits_y)
            z_q = z
            '''
            # Middle Area (Compression or Discretize)
            # TODO: Gross.. use brodcast instead!
            _t = tf.tile(tf.expand_dims(z_e,-2),[1,1,1,K,1]) #[batch,latent_h,latent_w,K,D]
            _e = tf.reshape(embeds,[1,1,1,K,D])
            _t = tf.norm(_t-_e,axis=-1)
            k = tf.argmin(_t,axis=-1) # -> [latent_h,latent_w]
            z_q = tf.gather(embeds,k)

            self.z_e = z_e # -> [batch,latent_h,latent_w,D]
            self.k = k # -> [batch,latent_h,latent_w]
            self.z_q = z_q # -> [batch,latent_h,latent_w,D]
            '''

            # Decoder Pass
            _t = z_q
            for block in dec_spec:
                _t = block(_t)
            self.p_x_z = _t

            # gumbel loss instead of Losses
            x_hat = self.p_x_z
            data_dim=576#784
            def gumbel_loss(x, x_hat):
                q_y = tf.reshape(logits_y, (-1, D))
                #q_y = tf.reshape(logits_y, (-1, N, M))
                q_y = tf.nn.softmax(q_y)
                log_q_y = tf.log(q_y + 1e-20)
                kl_tmp = q_y * (log_q_y - tf.log(1.0/(D)))
                KL = tf.reduce_sum(kl_tmp, axis=(1))
                #KL = tf.reduce_sum(kl_tmp, axis=(1, 2))
                elbo = tf.reduce_sum(data_dim * tf.nn.sigmoid_cross_entropy_with_logits(labels=x, logits=x_hat))
                elbo = elbo - KL 
                return tf.reduce_sum(elbo)
            self.loss = gumbel_loss(x, x_hat)

            '''
            # Losses
            self.recon = tf.reduce_mean((self.p_x_z - x)**2,axis=[0,1,2,3])
            self.vq = tf.reduce_mean(
                tf.norm(tf.stop_gradient(self.z_e) - z_q,axis=-1)**2,
                axis=[0,1,2])
            self.commit = tf.reduce_mean(
                tf.norm(self.z_e - tf.stop_gradient(z_q),axis=-1)**2,
                axis=[0,1,2])
            self.loss = self.recon + self.vq + beta * self.commit
            '''

            # NLL
            # TODO: is it correct impl?
            # it seems tf.reduce_prod(tf.shape(self.z_q)[1:2]) should be multipled
            # in front of log(1/K) if we assume uniform prior on z.
            self.nll = -1.*(tf.reduce_mean(tf.log(self.p_x_z),axis=[1,2,3]) + tf.log(1/tf.cast(K,tf.float32)))/tf.log(2.)

        #if( is_training ):
        if mode == 'train':
            with tf.variable_scope('backward'):
                '''
                # Decoder Grads
                decoder_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,dec_param_scope.name)
                decoder_grads = list(zip(tf.gradients(self.loss,decoder_vars),decoder_vars))
                # Encoder Grads
                encoder_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,enc_param_scope.name)
                grad_z = tf.gradients(self.recon,z_q)
                encoder_grads = [(tf.gradients(z_e,var,grad_z)[0]+beta*tf.gradients(self.commit,var)[0],var)
                                 for var in encoder_vars]
                # Embedding Grads
                embed_grads = list(zip(tf.gradients(self.vq,embeds),[embeds]))
                '''

                optimizer = tf.train.AdamOptimizer(lr)
                self.train_op = optimizer.minimize(self.loss)
                #self.train_op= optimizer.apply_gradients(decoder_grads+encoder_grads+embed_grads,global_step=global_step)
        elif mode == 'decode':
            # Another decoder pass that we can play with!
            size = self.z_e.get_shape()[1]
            Dim = self.z_e.get_shape()[-1]
            self.latent = tf.placeholder(tf.int32,[None,size,size])
            _t = tf.one_hot(self.latent, D,axis=-1)
            #_t = tf.gather(self.z_e,self.latent) #? need test consistence as following line
            #_t = tf.gather(embeds,self.latent)
            for block in dec_spec:
                _t = block(_t)
            self.gen = _t
        else: # i.e. transform data into latents
            #argmax_y = tf.reduce_max(tf.reshape(logits_y, (-1, D)), axis=-1, keep_dims=True)
            #self.argmax_y = tf.equal(tf.reshape(logits_y, (-1, D)), argmax_y)
            '''
            argmax_y = tf.reduce_max(logits_y, axis=-1, keep_dims=True)
            self.argmax_y = tf.equal(logits_y, argmax_y)
            self.k = self.argmax_y
            '''
            self.k = tf.argmax(logits_y, axis=-1)

        save_vars = {('train/'+'/'.join(var.name.split('/')[1:])).split(':')[0] : var for var in
                     tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES,param_scope.name) }
        #for name,var in save_vars.items():
        #    print(name,var)

        self.saver = tf.train.Saver(var_list=save_vars,max_to_keep = 3)

    def save(self,sess,dir,step=None):
        if(step is not None):
            self.saver.save(sess,dir+'/model.ckpt',global_step=step)
        else :
            self.saver.save(sess,dir+'/last.ckpt')

    def load(self,sess,model):
        self.saver.restore(sess,model)

class VQVAE():
    def __init__(self,lr,global_step,beta,
                 x,K,D,
                 arch_fn,
                 param_scope,is_training=False):
        with tf.variable_scope(param_scope):
            enc_spec,enc_param_scope,dec_spec,dec_param_scope = arch_fn(D)
            with tf.variable_scope('embed') :
                embeds = tf.get_variable('embed', [K,D],
                                        initializer=tf.truncated_normal_initializer(stddev=0.02))
                self.embeds = embeds

        with tf.variable_scope('forward') as forward_scope:
            # Encoder Pass
            _t = x
            for block in enc_spec :
                _t = block(_t)
            z_e = _t

            # Middle Area (Compression or Discretize)
            # TODO: Gross.. use brodcast instead!
            _t = tf.tile(tf.expand_dims(z_e,-2),[1,1,1,K,1]) #[batch,latent_h,latent_w,K,D]
            _e = tf.reshape(embeds,[1,1,1,K,D])
            _t = tf.norm(_t-_e,axis=-1)
            k = tf.argmin(_t,axis=-1) # -> [latent_h,latent_w]
            z_q = tf.gather(embeds,k)

            self.z_e = z_e # -> [batch,latent_h,latent_w,D]
            self.k = k
            self.z_q = z_q # -> [batch,latent_h,latent_w,D]

            # Decoder Pass
            _t = z_q
            for block in dec_spec:
                _t = block(_t)
            self.p_x_z = _t

            # Losses
            self.recon = tf.reduce_mean((self.p_x_z - x)**2,axis=[0,1,2,3])
            self.vq = tf.reduce_mean(
                tf.norm(tf.stop_gradient(self.z_e) - z_q,axis=-1)**2,
                axis=[0,1,2])
            self.commit = tf.reduce_mean(
                tf.norm(self.z_e - tf.stop_gradient(z_q),axis=-1)**2,
                axis=[0,1,2])
            self.loss = self.recon + self.vq + beta * self.commit

            # NLL
            # TODO: is it correct impl?
            # it seems tf.reduce_prod(tf.shape(self.z_q)[1:2]) should be multipled
            # in front of log(1/K) if we assume uniform prior on z.
            self.nll = -1.*(tf.reduce_mean(tf.log(self.p_x_z),axis=[1,2,3]) + tf.log(1/tf.cast(K,tf.float32)))/tf.log(2.)

        if( is_training ):
            with tf.variable_scope('backward'):
                # Decoder Grads
                decoder_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,dec_param_scope.name)
                decoder_grads = list(zip(tf.gradients(self.loss,decoder_vars),decoder_vars))
                # Encoder Grads
                encoder_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,enc_param_scope.name)
                grad_z = tf.gradients(self.recon,z_q)
                encoder_grads = [(tf.gradients(z_e,var,grad_z)[0]+beta*tf.gradients(self.commit,var)[0],var)
                                 for var in encoder_vars]
                # Embedding Grads
                embed_grads = list(zip(tf.gradients(self.vq,embeds),[embeds]))

                optimizer = tf.train.AdamOptimizer(lr)
                self.train_op= optimizer.apply_gradients(decoder_grads+encoder_grads+embed_grads,global_step=global_step)
        else :
            # Another decoder pass that we can play with!
            size = self.z_e.get_shape()[1]
            self.latent = tf.placeholder(tf.int64,[None,size,size])
            _t = tf.gather(embeds,self.latent)
            for block in dec_spec:
                _t = block(_t)
            self.gen = _t

        save_vars = {('train/'+'/'.join(var.name.split('/')[1:])).split(':')[0] : var for var in
                     tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES,param_scope.name) }
        #for name,var in save_vars.items():
        #    print(name,var)

        self.saver = tf.train.Saver(var_list=save_vars,max_to_keep = 3)

    def save(self,sess,dir,step=None):
        if(step is not None):
            self.saver.save(sess,dir+'/model.ckpt',global_step=step)
        else :
            self.saver.save(sess,dir+'/last.ckpt')

    def load(self,sess,model):
        self.saver.restore(sess,model)

class PixelCNN(object):
    def __init__(self,lr,global_step,grad_clip,
                 size, embeds, K, D,
                 num_classes, num_layers, num_maps,
                 is_training=True):
        import sys
        sys.path.append('pixelcnn')
        from workspace.tfvqvae.layers import GatedCNN
        #from layers import GatedCNN
        self.X = tf.placeholder(tf.int32,[None,size,size])
        #self.X = tf.placeholder(tf.float32,[None,size,size,D])

        if( num_classes is not None ):
            self.h = tf.placeholder(tf.int32,[None,])
            onehot_h = tf.one_hot(self.h,num_classes,axis=-1)
        else:
            onehot_h = None

        '''
        if( embeds is not None ):
            X_processed = tf.gather(tf.stop_gradient(embeds),self.X)
        else:
            embeds = tf.get_variable('embed', [K,D],
                                    initializer=tf.truncated_normal_initializer(stddev=0.02))
            X_processed = tf.gather(embeds,self.X)
        '''
        X_processed = tf.one_hot(self.X, D,axis=-1) 
        v_stack_in, h_stack_in = X_processed, X_processed
        for i in range(num_layers):
            filter_size = 3 if i > 0 else 7
            mask = 'b' if i > 0 else 'a'
            residual = True if i > 0 else False
            i = str(i)
            with tf.variable_scope("v_stack"+i):
                v_stack = GatedCNN([filter_size, filter_size, num_maps], v_stack_in, False, mask=mask, conditional=onehot_h).output()
                #v_stack = GatedCNN([filter_size, filter_size, num_maps], v_stack_in, mask=mask, conditional=onehot_h).output()
                v_stack_in = v_stack

            with tf.variable_scope("v_stack_1"+i):
                v_stack_1 = GatedCNN([1, 1, num_maps], v_stack_in, False, gated=False, mask=mask).output()
                #v_stack_1 = GatedCNN([1, 1, num_maps], v_stack_in, gated=False, mask=mask).output()

            with tf.variable_scope("h_stack"+i):
                h_stack = GatedCNN([1, filter_size, num_maps], h_stack_in, True, payload=v_stack_1, mask=mask, conditional=onehot_h).output()
                #h_stack = GatedCNN([1, filter_size, num_maps], h_stack_in, payload=v_stack_1, mask=mask, conditional=onehot_h).output()

            with tf.variable_scope("h_stack_1"+i):
                h_stack_1 = GatedCNN([1, 1, num_maps], h_stack, True, gated=False, mask=mask).output()
                #h_stack_1 = GatedCNN([1, 1, num_maps], h_stack, gated=False, mask=mask).output()
                if residual:
                    h_stack_1 += h_stack_in # Residual connection
                h_stack_in = h_stack_1

        with tf.variable_scope("fc_1"):
            #fc1 = GatedCNN([1, 1, num_maps], h_stack_in, gated=False, mask='b').output()
            fc1 = GatedCNN([1, 1, num_maps], h_stack_in, True, gated=False, mask='b').output()

        with tf.variable_scope("fc_2"):
            #self.fc2 = GatedCNN([1, 1, K], fc1, gated=False, mask='b', activation=False).output()
            self.fc2 = GatedCNN([1, 1, D], fc1, True, gated=False, mask='b', activation=False).output()
            self.dist = tf.distributions.Categorical(logits=self.fc2)
            self.sampled = self.dist.sample()
            self.log_prob = self.dist.log_prob(self.sampled)

        #loss_per_batch = tf.reduce_sum(tf.nn.softmax_cross_entropy_with_logits(logits=self.fc2,
        loss_per_batch = tf.reduce_sum(tf.nn.sparse_softmax_cross_entropy_with_logits(logits=self.fc2,
                                                                                      labels=self.X),axis=[1,2])
        self.loss = tf.reduce_mean(loss_per_batch,axis=0)

        save_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,tf.contrib.framework.get_name_scope())
        self.saver = tf.train.Saver(var_list=save_vars,max_to_keep = 3)

        if( is_training ):
            with tf.variable_scope('backward'):
                optimizer = tf.train.AdamOptimizer(lr)

                gradients = optimizer.compute_gradients(self.loss,var_list=save_vars)
                if( grad_clip is None ):
                    clipped_gradients = gradients
                else :
                    clipped_gradients = [(tf.clip_by_value(_[0], -grad_clip, grad_clip), _[1]) for _ in gradients]
                    #clipped_gradients = [(tf.clip_by_average_norm(_[0], grad_clip), _[1]) for _ in gradients]
                self.train_op = optimizer.apply_gradients(clipped_gradients,global_step)
        #for var in save_vars:
        #    print(var,var.name)

    def sample_from_prior(self,sess,classes,batch_size):
        # Generates len(classes)*batch_size Z samples.
        size = self.X.get_shape()[1]
        D = self.X.get_shape()[-1]
        feed_dict={
            self.X: np.zeros([len(classes)*batch_size,size,size],np.int32)
            #self.X: np.zeros([len(classes)*batch_size,size,size,D],np.float32)
        }
        if( classes is not None ):
            feed_dict[self.h] = np.repeat(classes,batch_size).astype(np.int32)

        log_probs = np.zeros((len(classes)*batch_size,))
        for i in xrange(size):
            for j in xrange(size):
                sampled,log_prob = sess.run([self.sampled,self.log_prob],feed_dict=feed_dict)
                feed_dict[self.X][:,i,j]= sampled[:,i,j]
                log_probs += log_prob[:,i,j]
        return feed_dict[self.X], log_probs

    def save(self,sess,dir,step=None):
        if(step is not None):
            self.saver.save(sess,dir+'/model-pixelcnn.ckpt',global_step=step)
        else :
            self.saver.save(sess,dir+'/last-pixelcnn.ckpt')

    def load(self,sess,model):
        self.saver.restore(sess,model)

if __name__ == "__main__":
    with tf.variable_scope('params') as params:
        pass

    x = tf.placeholder(tf.float32,[None,32,32,3])
    global_step = tf.Variable(0, trainable=False)

    net = VQVAE(0.1,global_step,0.1,x,20,256,_cifar10_arch,params,True)

    with tf.variable_scope('pixelcnn'):
        latent = tf.placeholder(tf.int32,[None,3,3])
        embeds = net.embeds

        pixelcnn = PixelCNN(0.1,global_step,1.0,
                            3,embeds,20,32,
                            True,10,20)

    init_op = tf.group(tf.global_variables_initializer(),
                    tf.local_variables_initializer())

    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    sess = tf.Session(config=config)
    sess.graph.finalize()
    sess.run(init_op)

    #print(sess.run(net.train_op,feed_dict={x:np.random.random((10,32,32,3))}))
    sampled,log_prob = pixelcnn.sample_from_prior(sess,np.arange(10),1)
    print(sampled[0], np.exp(log_prob[0]))

