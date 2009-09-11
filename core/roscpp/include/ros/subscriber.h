/*
 * Copyright (C) 2008, Morgan Quigley and Willow Garage, Inc.
 * 
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *   * Redistributions of source code must retain the above copyright notice,
 *     this list of conditions and the following disclaimer.
 *   * Redistributions in binary form must reproduce the above copyright
 *     notice, this list of conditions and the following disclaimer in the
 *     documentation and/or other materials provided with the distribution.
 *   * Neither the names of Stanford University or Willow Garage, Inc. nor the names of its
 *     contributors may be used to endorse or promote products derived from
 *     this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

#ifndef ROSCPP_SUBSCRIBER_H
#define ROSCPP_SUBSCRIBER_H

#include "ros/data_handler.h"
#include "ros/common.h"

#include <boost/thread/mutex.hpp>
#include <boost/shared_array.hpp>
#include <boost/weak_ptr.hpp>
#include <boost/enable_shared_from_this.hpp>

#include <queue>

namespace ros
{
class Message;
class Subscription;
typedef boost::shared_ptr<Subscription> SubscriptionPtr;
typedef boost::weak_ptr<Subscription> SubscriptionWPtr;
class Connection;
typedef boost::shared_ptr<Connection> ConnectionPtr;

/**
 * \brief Handles a connection to a single publisher on a given topic.  Receives messages from a publisher
 * and hands them off to its parent Subscription
 */
class Subscriber : public DataHandler, public boost::enable_shared_from_this<Subscriber>
{
public:
  class Stats
  {
  public:
    uint64_t bytes_received_, messages_received_, drops_;
    Stats()
    : bytes_received_(0), messages_received_(0), drops_(0) { }
  };


  Subscriber(const SubscriptionPtr& parent, const std::string& xmlrpc_uri);
  virtual ~Subscriber();

  // Overrides from DataHandler
  virtual bool initialize(const ConnectionPtr& connection);
  virtual bool handleHeader(const Header& header);

  const ConnectionPtr& getConnection() { return connection_; }

  std::string getTransportType();
  const Stats &getStats() { return stats_; }
  const std::string& getPublisherXMLRPCURI();
  inline int getConnectionID() const { return connection_id_; }

private:
  void onConnectionDropped(const ConnectionPtr& conn);

  /**
   * \brief Handles handing off a received message to the subscription, where it will be deserialized and called back
   */
  void handleMessage(const boost::shared_array<uint8_t>& buffer, size_t num_bytes);

  void onHeaderWritten(const ConnectionPtr& conn);
  void onMessageLength(const ConnectionPtr& conn, const boost::shared_array<uint8_t>& buffer, uint32_t size);
  void onMessage(const ConnectionPtr& conn, const boost::shared_array<uint8_t>& buffer, uint32_t size);

  ConnectionPtr connection_;
  SubscriptionWPtr parent_;
  unsigned int connection_id_;
  std::string publisher_xmlrpc_uri_;

  Stats stats_;
};

} // namespace ros

#endif // ROSCPP_SUBSCRIBER_H



