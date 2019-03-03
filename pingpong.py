from mpi4py import MPI
import logging
import threading
import time
import random
from Tkinter import Tk, Label, Button

mpi_comm = MPI.COMM_WORLD
rank = mpi_comm.rank

class GetRank(logging.Filter):
    def filter(self, record):
        record.rank = rank
        record.seconds = time.strftime('%H:%M:%S', time.gmtime())
        record.round_ping = m.ping_round
        record.round_pong = m.pong_round
        return True

logging.basicConfig(
    format='%(seconds)s | %(rank)s | Ping: %(round_ping)s | Pong: %(round_pong)s | %(message)s')
log = logging.getLogger(__name__)
log.addFilter(GetRank())


class MonitorState:
    IDLE, \
    WAITING, \
    IN_CRITICAL_SECTION, \
    = range(3)

class MsgType:
    PING, \
    PONG, \
    = range(2)

class Monitor: 
    def __init__(self,id):
        self.id = id
        self.state = MonitorState.IDLE
        self.lost_next_ping = False
        self.lost_next_pong = False
        self.ping = 0
        self.pong = 0
        self.conv = threading.Lock()
        self.data = threading.Lock()
        self.sync_listener = threading.Lock()
        self.sync_listener.acquire()
        self.m = 0
        self.ping_round = 0
        self.pong_round = 0
        #time.sleep(1)
        mpi_comm.barrier()       
        self.pingowner = False
        self.pongowner = False
        self.next_node = (rank+1) % mpi_comm.size
        
        if (rank == mpi_comm.size-1 ):                    #tokeny zaczynaja zycie w procesie N
            self.incarnate()
            time.sleep(0.5)
            mpi_comm.send(self.ping,dest=self.next_node, tag=MsgType.PING)
            mpi_comm.send(self.pong,dest=self.next_node, tag=MsgType.PONG)
            # self.pingowner = True
            # self.pongowner = True
            # self.incarnate()
            # self.state = MonitorState.IN_CRITICAL_SECTION

        self._listener = threading.Thread(target=self.listener)
        self._listener.start()


    def regenerate(self, val):
        self.ping = abs(val)
        self.pong = -1 * self.ping


    def incarnate(self):
        self.ping = self.ping + 1
        self.pong = -1 * self.ping

    def listener(self):
        msg = 0
        self.sync_listener.acquire()
        time.sleep(1)
        statuss = MPI.Status()
        while True:
            msg = mpi_comm.recv(tag=MPI.ANY_TAG,status=statuss)
            if (statuss.Get_tag() == MsgType.PING):
                self.ping_round += 1
                if (msg < abs(self.m)):
                    log.warning('GOT OLD PING')
                else:
                    log.warning('GOT PING')
                    self.pingowner = True
                    self.data.acquire()

                    if (self.m == msg):
                        self.regenerate(msg)
                        log.warning('REGENERATE PONG %i',self.pong)
                        self.send_pong(False)
                    else:
                        if (self.m < msg):
                            self.regenerate(msg)

                    self.state = MonitorState.IN_CRITICAL_SECTION
                    self.conv.release()
                    
                    self.data.release()
                    

            elif statuss.Get_tag() == MsgType.PONG:
                self.pong_round += 1
                if (abs(msg) < abs(self.m)):
                    log.warning('GOT OLD PONG')
                else:
                    log.warning('GOT PONG')

                    self.data.acquire()

                    inc = False

                    if self.pingowner == True:
                        inc = True
                        self.incarnate()
                        log.warning('INCARNATE PINGPONG %i',self.ping)
                    elif self.m == msg:
                        self.regenerate(msg)
                        log.warning('REGENERATE PING %i',self.ping)
                        self.send_ping(False)
                    elif (abs(self.m) < abs(msg)):
                        self.regenerate(msg)

                    self.data.release()

                    if (inc):
                        while (self.pingowner):
                            time.sleep(0.5)

                        if debug: 
                            if self.lost_next_pong:
                                log.warning('PONG LOST ON DEMAND!')
                                self.m = self.pong
                                self.pongowner = False
                                self.lost_next_pong = False
                            else:
                                
                                self.send_pong(True)
                        else:
                            
                            self.send_pong(True)
                            
                    else:
                        if debug: 
                            if self.lost_next_pong:
                                log.warning('PONG LOST ON DEMAND!')
                                self.m = self.pong
                                self.pongowner = False
                                self.lost_next_pong = False
                            else:
                                self.send_pong(True)
                        else:
                            self.send_pong(True)


    def send_ping(self,save):
        log.warning('SEND PING TO '+str(self.next_node))
        if save:
            self.m = self.ping
        mpi_comm.send(self.ping,dest=self.next_node, tag=MsgType.PING)
        self.pingowner = False
        

    def send_pong(self,save):
        time.sleep(0.5)
        log.warning('SEND PONG TO '+str(self.next_node))
        if save:
            self.m = self.pong
        mpi_comm.send(self.pong,dest=self.next_node, tag=MsgType.PONG)
        self.pongowner = False

    def lost_ping(self):
        self.lost_next_ping = True
        log.warning('LOST PING CLICKED!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    def lost_pong(self):
        self.lost_next_pong = True
        log.warning('LOST PONG CLICKED!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')


if __name__ == '__main__':

    m = Monitor(1)
    debug = True
    ROOT = Tk()
    LABEL = Label(ROOT, text="Input for proces rank: "+str(rank))
    LABEL.pack()
    btn = Button(ROOT, text="Zgub PING",command= m.lost_ping)
    btn.pack()
    btn2 = Button(ROOT, text="Zgub PONG",command= m.lost_pong)
    btn2.pack()
    m.sync_listener.release()

    while True:
        ROOT.update()
        m.conv.acquire()
        if(m.state == MonitorState.IN_CRITICAL_SECTION):
            log.warning('INSIDE CS')
            time.sleep(random.choice([1.3,2]))
            #time.sleep(2)
            m.data.acquire()



            if debug: 
                if m.lost_next_ping:
                    log.warning('PING LOST ON DEMAND!')
                    m.lost_next_ping = False
                    m.m = m.ping
                    m.pingowner = False
                else:
                    m.send_ping(True)
            else:
                m.send_ping(True)

            m.state = MonitorState.WAITING
            m.data.release()


        else:
            m.conv.acquire()
            m.conv.release()
    

