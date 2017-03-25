# -*- Mode:python; c-file-style:"gnu"; indent-tabs-mode:nil -*- */
#
# Copyright (C) 2017 Regents of the University of California.
# Author: Jeff Thompson <jefft0@remap.ucla.edu>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# A copy of the GNU Lesser General Public License is in the file COPYING.

"""
This module defines the NameSynceHandler class which uses ChronoSync to run
the NameSync protocol to add announced names to a NameSpace object.
"""

import logging
import chatbuf_pb2
import time
from pyndn.sync import ChronoSync2013
from pyndn import Name
from pyndn import Interest
from pyndn import Data
from pyndn import Face
from pyndn.security import KeyType
from pyndn.security import KeyChain
from pyndn.security.identity import IdentityManager
from pyndn.security.identity import MemoryIdentityStorage
from pyndn.security.identity import MemoryPrivateKeyStorage
from pyndn.security.policy import NoVerifyPolicyManager
from pyndn.util import Blob

class NameSyncHandler(object):
    """
    Create a NameSynceHandler object to attach to the given Namespace. This
    holds an internal ChronoSync2013 with the given values. This uses the Face
    which must already be set for the Namespace (or one of its parents).
    """
    def __init__(self, namespace, userPrefix, keyChain, certificateName):
        face = namespace._getFace()
        self.nameSync_ = NameSyncHandler.NameSync(namespace, userPrefix, face, keyChain, certificateName)

    def announce(self, name):
        """
        Send a chat message.
        """
        # TODO: Should this instead be triggered when a child is added in the producer app?
        self.nameSync_.announce(name)

    class NameSync(object):
        def __init__(self, namespace, userPrefix, face, keyChain,certificateName):
            self._namespace = namespace
            self._namespacePrefix = namespace.getName()
            self._userPrefix = userPrefix
            self._face = face
            self._keyChain = keyChain
            self._certificateName = certificateName

            self._messageCache = [] # of CachedMessage
            self._maxMessageCacheLength = 100
            self._isRecoverySyncState = False
            self._syncLifetime = 5000.0 # milliseconds

            self._sync = ChronoSync2013(
               self._sendInterest, self._initial, Name(userPrefix),
               Name("/ndn/broadcast/namesync").append(self._namespacePrefix), 0,
               face, keyChain, certificateName, self._syncLifetime,
               self._onRegisterFailed)

            face.registerPrefix(self._userPrefix, self._onInterest, self._onRegisterFailed)

        def announce(self, name):
            """
            Send a chat message.
            """

            # Ignore an empty message.
            # Forming Sync Data Packet.
            if name != "":
                self._sync.publishNextSequenceNo()
                self._messageCacheAppend(chatbuf_pb2.ChatMessage.ADD, name)
                print("announced: " + name)

        @staticmethod
        def getNowMilliseconds():
            """
            Get the current time in milliseconds.

            :return: The current time in milliseconds since 1/1/1970, including
              fractions of a millisecond.
            :rtype: float
            """
            return time.time() * 1000.0

        def _onRegisterFailed(prefix):
            print("Register failed for prefix " + prefix.toUri())

        def _initial(self):
            return

        def _sendInterest(self, syncStates, isRecovery):
            """
            Send a Chat Interest to fetch chat messages after the user gets the Sync
            data packet back but will not send interest.
            """
            # This is used by _onData to decide whether to display the chat messages.
            self._isRecoverySyncState = isRecovery

            sendList = []       # of str
            sessionNoList = []  # of int
            sequenceNoList = [] # of int
            for j in range(len(syncStates)):
                syncState = syncStates[j]
                nameComponents = Name(syncState.getDataPrefix())
                tempName = nameComponents.get(-1).toEscapedString()
                sessionNo = syncState.getSessionNo()
                if not tempName == Name(self._userPrefix)[-1].toEscapedString():
                    index = -1
                    for k in range(len(sendList)):
                        if sendList[k] == syncState.getDataPrefix():
                            index = k
                            break

                    if index != -1:
                        sessionNoList[index] = sessionNo
                        sequenceNoList[index] = syncState.getSequenceNo()
                    else:
                        sendList.append(syncState.getDataPrefix())
                        sessionNoList.append(sessionNo)
                        sequenceNoList.append(syncState.getSequenceNo())

            for i in range(len(sendList)):
                uri = (sendList[i] + "/" + str(sessionNoList[i]) + "/" +
                  str(sequenceNoList[i]))
                interest = Interest(Name(uri))
                interest.setInterestLifetimeMilliseconds(self._syncLifetime)
                self._face.expressInterest(interest, self._onData, self._chatTimeout)

        def _onInterest(self, prefix, interest, face, interestFilterId, filter):
            """
            Send back a Chat Data Packet which contains the user's message.
            """
            content = chatbuf_pb2.ChatMessage()
            sequenceNo = int(
              interest.getName()[-1].toEscapedString())
            gotContent = False
            for i in range(len(self._messageCache) - 1, -1, -1):
                message = self._messageCache[i]
                if message.sequenceNo == sequenceNo:
                    if message.messageType == chatbuf_pb2.ChatMessage.ADD:
                        # Use setattr because "from" is a reserved keyword.
                        content.data = message.message
                        content.type = message.messageType
                        content.timestamp = int(round(message.time / 1000.0))

                    gotContent = True
                    break

            if gotContent:
                # TODO: Check if this works in Python 3.
                array = content.SerializeToString()
                data = Data(interest.getName())
                data.setContent(Blob(array))
                self._keyChain.sign(data, self._certificateName)
                try:
                    face.putData(data)
                except Exception as ex:
                    logging.getLogger(__name__).error(
                      "Error in transport.send: %s", str(ex))
                    return

        def _onData(self, interest, data):
            """
            Process the incoming Chat data.
            """
            # TODO: Check if this works in Python 3.
            content = chatbuf_pb2.ChatMessage()
            content.ParseFromString(data.getContent().toRawStr())
            prefix = data.getName().getPrefix(-2).toUri()
            sessionNo = int(data.getName().get(-2).toEscapedString())
            sequenceNo = int(data.getName().get(-1).toEscapedString())

            if (content.type == chatbuf_pb2.ChatMessage.ADD):
                print("got: "+content.data)
                self._namespace.getChild(content.data)

        @staticmethod
        def _chatTimeout(interest):
            return

        def _messageCacheAppend(self, messageType, message):
            """
            Append a new CachedMessage to messageCache_, using given messageType and
            message, the sequence number from _sync.getSequenceNo() and the current
            time. Also remove elements from the front of the cache as needed to keep
            the size to _maxMessageCacheLength.
            """
            self._messageCache.append(self._CachedMessage(
              self._sync.getSequenceNo(), messageType, message,
              self.getNowMilliseconds()))
            while len(self._messageCache) > self._maxMessageCacheLength:
              self._messageCache.pop(0)

        @staticmethod
        def _getRandomString():
            """
            Generate a random name for ChronoSync.
            """
            seed = "qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM0123456789"
            result = ""
            for i in range(10):
              # Using % means the distribution isn't uniform, but that's OK.
              position = random.randrange(256) % len(seed)
              result += seed[position]

            return result

        @staticmethod
        def _dummyOnData(interest, data):
            """
            This is a do-nothing onData for using expressInterest for timeouts.
            This should never be called.
            """
            pass

        class _CachedMessage(object):
            def __init__(self, sequenceNo, messageType, message, time):
                self.sequenceNo = sequenceNo
                self.messageType = messageType
                self.message = message
                self.time = time