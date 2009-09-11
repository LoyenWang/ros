/*********************************************************************
* Software License Agreement (BSD License)
*
*  Copyright (c) 2008, Willow Garage, Inc.
*  All rights reserved.
*
*  Redistribution and use in source and binary forms, with or without
*  modification, are permitted provided that the following conditions
*  are met:
*
*   * Redistributions of source code must retain the above copyright
*     notice, this list of conditions and the following disclaimer.
*   * Redistributions in binary form must reproduce the above
*     copyright notice, this list of conditions and the following
*     disclaimer in the documentation and/or other materials provided
*     with the distribution.
*   * Neither the name of Willow Garage, Inc. nor the names of its
*     contributors may be used to endorse or promote products derived
*     from this software without specific prior written permission.
*
*  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
*  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
*  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
*  FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
*  COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
*  INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
*  BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
*  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
*  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
*  LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
*  ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
*  POSSIBILITY OF SUCH DAMAGE.
********************************************************************/

#include "rosout_panel.h"
#include "rosout_setup_dialog.h"
#include "rosout_list_control.h"

#include <wx/wx.h>
#include <wx/aui/auibook.h>
#include <wx/richtext/richtextctrl.h>

#include <ros/node.h>

#include <sstream>
#include <algorithm>

#include <boost/bind.hpp>

namespace rxtools
{

RosoutPanel::RosoutPanel(wxWindow* parent)
: RosoutPanelBase(parent)
, enabled_(false)
, topic_("/rosout_agg")
, message_id_counter_(0)
, max_messages_(20000)
, use_regex_(false)
, valid_include_regex_(false)
, valid_exclude_regex_(false)
, needs_refilter_(false)
, refilter_timer_(0.0f)
{
  ros_node_ = ros::Node::instance();

  /// @todo This should go away once creation of the ros::Node is more well-defined
  if (!ros_node_)
  {
    int argc = 0;
    ros::init(argc, 0);
    ros_node_ = new ros::Node("RosoutPanel", ros::Node::DONT_HANDLE_SIGINT);
  }
  ROS_ASSERT(ros_node_);

  process_timer_ = new wxTimer(this);
  process_timer_->Start(100);

  Connect(process_timer_->GetId(), wxEVT_TIMER, wxTimerEventHandler(RosoutPanel::onProcessTimer), NULL, this);

  table_->setMessageFunction(boost::bind(&RosoutPanel::getMessageByIndex, this, _1));
}

RosoutPanel::~RosoutPanel()
{
  unsubscribe();

  Disconnect(process_timer_->GetId(), wxEVT_TIMER, wxTimerEventHandler(RosoutPanel::onProcessTimer), NULL, this);

  delete process_timer_;

  clear();
}

void RosoutPanel::clear()
{
  table_->SetItemCount(0);
  messages_.clear();
  ordered_messages_.clear();
}

void RosoutPanel::setEnabled(bool enabled)
{
  if (enabled_ == enabled)
  {
    return;
  }

  enabled_ = enabled;
  if (enabled)
  {
    subscribe();
  }
  else
  {
    unsubscribe();
  }
}

void RosoutPanel::subscribe()
{
  if (!enabled_ || topic_.empty())
  {
    return;
  }

  ros_node_->subscribe(topic_, message_, &RosoutPanel::incomingMessage, this, 0);
}

void RosoutPanel::unsubscribe()
{
  if (topic_.empty())
  {
    return;
  }

  ros_node_->unsubscribe(topic_, &RosoutPanel::incomingMessage, this);
}

void RosoutPanel::setTopic(const std::string& topic)
{
  if (topic == topic_)
  {
    return;
  }

  unsubscribe();

  topic_ = topic;

  subscribe();
}

void RosoutPanel::onProcessTimer(wxTimerEvent& evt)
{
  processMessages();

  refilter_timer_ += 0.1f;
  if (needs_refilter_ && refilter_timer_ > 1.0f)
  {
    refilter_timer_ = 0.0f;
    needs_refilter_ = false;
    refilter();
  }
}

void RosoutPanel::onClear(wxCommandEvent& event)
{
  clear();
}

void RosoutPanel::addMessageToTable(const roslib::Log& message, uint32_t id)
{
  ordered_messages_.push_back(id);
  table_->SetItemCount(ordered_messages_.size());
}

const roslib::Log& RosoutPanel::getMessageByIndex(uint32_t index) const
{
  ROS_ASSERT(index < ordered_messages_.size());

  M_IdToMessage::const_iterator it = messages_.find(ordered_messages_[index]);
  ROS_ASSERT(it != messages_.end());

  return it->second;
}

bool RosoutPanel::include(const std::string& str) const
{
  // If the include filter is empty, that means we should include everything
  if (include_filter_.empty())
  {
    return true;
  }

  bool include_match = false;

  if (use_regex_)
  {
    if (valid_include_regex_)
    {
      include_match = boost::regex_match(str, include_regex_);
    }
  }
  else
  {
    include_match = str.find(include_filter_) != std::string::npos;
  }

  return include_match;
}

bool RosoutPanel::exclude(const std::string& str) const
{
  if (exclude_filter_.empty())
  {
    return false;
  }

  bool exclude_match = false;

  if (use_regex_)
  {
    if (valid_exclude_regex_)
    {
      exclude_match = boost::regex_match(str, exclude_regex_);
    }
  }
  else
  {
    exclude_match = str.find(exclude_filter_) != std::string::npos;
  }

  return exclude_match;
}

bool RosoutPanel::include(const V_string& strs) const
{
  V_string::const_iterator it = strs.begin();
  V_string::const_iterator end = strs.end();
  for (; it != end; ++it)
  {
    if (include(*it))
    {
      return true;
    }
  }

  return false;
}

bool RosoutPanel::exclude(const V_string& strs) const
{
  V_string::const_iterator it = strs.begin();
  V_string::const_iterator end = strs.end();
  for (; it != end; ++it)
  {
    if (exclude(*it))
    {
      return true;
    }
  }

  return false;
}

bool RosoutPanel::filter(uint32_t id) const
{
  // Early out if both include and exclude filters are empty
  if (include_filter_.empty() && exclude_filter_.empty())
  {
    return true;
  }

  M_IdToMessage::const_iterator it = messages_.find(id);
  ROS_ASSERT(it != messages_.end());

  const roslib::Log& message = it->second;

  // Turn non-string values into strings so we can match against them
  std::stringstream line;
  line << message.line;
  std::stringstream time;
  time << message.header.stamp;

  // If any of the exclusions match, this message should be excluded
  if (exclude(message.name) || exclude(message.msg) || exclude(message.file) || exclude(message.function) || exclude(line.str()) || exclude(message.topics)
      || exclude(time.str()) || exclude((const char*) table_->getSeverityText(message).fn_str()))
  {
    return false;
  }

  // If any of the inclusions match, this message should be included
  return include(message.name) || include(message.msg) || include(message.file) || include(message.function) || include(line.str()) || include(message.topics)
      || include(time.str()) || include((const char*) table_->getSeverityText(message).fn_str());
}

void RosoutPanel::refilter()
{
  table_->Freeze();

  /// @todo wxListCtrl::GetScrollRange doesn't work, so I have to work around it.  Switch to use GetScrollPos and GetScrollRange once Bug #10155 in the wxWidgets trac is fixed.

  bool scroll_to_bottom = false;

  // wxListCtrl on the mac doesn't implement GetCountPerPage() correctly, so disable autoscrolling on the mac
#ifndef __WXMAC__
  int count_per_page = table_->GetCountPerPage();
  int scroll_pos = table_->GetScrollPos(wxVERTICAL);
  if (scroll_pos + count_per_page >= table_->GetItemCount())
  {
    scroll_to_bottom = true;
  }
#endif

  ordered_messages_.clear();
  M_IdToMessage::iterator it = messages_.begin();
  M_IdToMessage::iterator end = messages_.end();
  for (; it != end; ++it)
  {
    uint32_t id = it->first;
    roslib::Log& message = it->second;

    if (filter(id))
    {
      addMessageToTable(message, id);
    }
  }

  table_->SetItemCount(ordered_messages_.size());

  if (scroll_to_bottom && !ordered_messages_.empty())
  {
    table_->EnsureVisible(table_->GetItemCount() - 1);
  }

  // This for some reason prevents the control from flickering: http://wiki.wxwidgets.org/Flicker-Free_Drawing#No-flickering_for_wxListCtrl_with_wxLC_REPORT_.7C_wxLC_VIRTUAL_style
  wxIdleEvent idle;
  wxTheApp->SendIdleEvents(this, idle);

  table_->Thaw();
}

void RosoutPanel::popMessage()
{
  M_IdToMessage::iterator it = messages_.begin();
  if (!ordered_messages_.empty() && ordered_messages_.front() == it->first)
  {

    ordered_messages_.erase(ordered_messages_.begin());
    table_->SetItemCount(ordered_messages_.size());
  }

  messages_.erase(it);
}

void RosoutPanel::processMessage(const roslib::Log& message)
{
  uint32_t id = message_id_counter_++;

  messages_.insert(std::make_pair(id, message));

  if (filter(id))
  {
    addMessageToTable(message, id);
  }

  if (messages_.size() > max_messages_)
  {
    popMessage();
  }
}

void RosoutPanel::processMessages()
{
  V_Log local_queue;
  {
    boost::mutex::scoped_lock lock(queue_mutex_);

    local_queue.swap(message_queue_);
  }

  if (local_queue.empty())
  {
    return;
  }

  table_->Freeze();

  // determine if the scrollbar is at the bottom of its range
  /// @todo wxListCtrl::GetScrollRange doesn't work, so I have to work around it.  Switch to use GetScrollPos and GetScrollRange once Bug #10155 in the wxWidgets trac is fixed.
  bool scroll_to_bottom = false;
  // wxListCtrl on the mac doesn't implement GetCountPerPage() correctly, so disable autoscrolling on the mac
#ifndef __WXMAC__
  int count_per_page = table_->GetCountPerPage();
  int scroll_pos = table_->GetScrollPos(wxVERTICAL);
  //printf("scroll_pos: %d, count_per_page: %d, scroll range: %d\n", scroll_pos, count_per_page, table_->GetScrollRange(wxVERTICAL));
  if (scroll_pos + count_per_page >= table_->GetItemCount())
  {
    scroll_to_bottom = true;
  }
#endif

  V_Log::iterator it = local_queue.begin();
  V_Log::iterator end = local_queue.end();
  for (; it != end; ++it)
  {
    roslib::Log& message = *it;

    processMessage(message);
  }

  // If the scrollbar was at the bottom of its range, make sure we're scrolled all the way down
  if (scroll_to_bottom && !ordered_messages_.empty())
  {
    table_->EnsureVisible(table_->GetItemCount() - 1);
  }

  // This for some reason prevents the control from flickering: http://wiki.wxwidgets.org/Flicker-Free_Drawing#No-flickering_for_wxListCtrl_with_wxLC_REPORT_.7C_wxLC_VIRTUAL_style
  wxIdleEvent idle;
  wxTheApp->SendIdleEvents(this, idle);

  table_->Thaw();
}

void RosoutPanel::incomingMessage()
{
  boost::mutex::scoped_lock lock(queue_mutex_);

  message_queue_.push_back(message_);
}

void RosoutPanel::onPause(wxCommandEvent& evt)
{
  if (evt.IsChecked())
  {
    process_timer_->Stop();
  }
  else
  {
    process_timer_->Start(100);
  }
}

void RosoutPanel::onSetup(wxCommandEvent& evt)
{
  RosoutSetupDialog dialog(this, ros_node_, topic_, max_messages_);

  if (dialog.ShowModal() == wxOK)
  {
    setTopic(dialog.getTopic());
    setBufferSize(dialog.getBufferSize());
  }
}

void RosoutPanel::setBufferSize(uint32_t size)
{
  max_messages_ = size;
  while (messages_.size() >= max_messages_)
  {
    popMessage();
  }
}

void RosoutPanel::setInclude(const std::string& filter)
{
  include_filter_ = filter;

  include_text_->SetBackgroundColour(*wxWHITE);

  valid_include_regex_ = true;

  if (use_regex_ && !filter.empty())
  {
    try
    {
      include_regex_ = boost::regex(filter);
    }
    catch (std::runtime_error&)
    {
      include_text_->SetBackgroundColour(*wxRED);
      valid_include_regex_ = false;
    }
  }

  needs_refilter_ = true;
}

void RosoutPanel::setExclude(const std::string& filter)
{
  exclude_filter_ = filter;

  exclude_text_->SetBackgroundColour(*wxWHITE);

  valid_exclude_regex_ = true;

  if (use_regex_ && !filter.empty())
  {
    try
    {
      exclude_regex_ = boost::regex(filter);
    }
    catch (std::runtime_error&)
    {
      exclude_text_->SetBackgroundColour(*wxRED);
      valid_exclude_regex_ = false;
    }
  }

  needs_refilter_ = true;
}

void RosoutPanel::onIncludeText(wxCommandEvent& event)
{
  setInclude((const char*) include_text_->GetValue().fn_str());
}

void RosoutPanel::onExcludeText(wxCommandEvent& event)
{
  setExclude((const char*) exclude_text_->GetValue().fn_str());
}

void RosoutPanel::onRegexChecked(wxCommandEvent& event)
{
  use_regex_ = regex_checkbox_->GetValue();

  setInclude(include_filter_);
  setExclude(exclude_filter_);
}

} // namespace rxtools
