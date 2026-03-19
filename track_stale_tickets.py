import sys
import csv
from datetime import datetime, timezone, timedelta

def get_resolver_group_members(group_name):
    """Get members of a resolver group"""
    try:
        from TicketingReadActions import TicketingReadActions
        result = TicketingReadActions(
            action="get-resolver-group-details",
            input={"groupName": group_name},
            explanation="Getting resolver group members for stale ticket tracking"
        )
        
        members = set()
        if 'members' in result:
            for member in result['members']:
                members.add(member.get('username', '').lower())
        return members
    except Exception as e:
        print(f"Error getting resolver group members: {e}", file=sys.stderr)
        return set()

def search_tickets(group_name):
    """Search for open tickets assigned to resolver group"""
    try:
        from TicketingReadActions import TicketingReadActions
        result = TicketingReadActions(
            action="search-tickets",
            input={
                "assignedGroup": [group_name],
                "status": ["Open", "Assigned", "Researching", "Work In Progress", "Pending"],
                "currentSeverity": [2, 2.5, 3],
                "rows": 100
            },
            explanation="Searching for open tickets to check for staleness"
        )
        
        return result.get('tickets', [])
    except Exception as e:
        print(f"Error searching tickets: {e}", file=sys.stderr)
        return []

def get_ticket_details(ticket_id):
    """Get detailed ticket information including comments"""
    try:
        from TicketingReadActions import TicketingReadActions
        result = TicketingReadActions(
            action="get-ticket",
            input={"ticketId": ticket_id},
            explanation="Getting ticket details to check comment history"
        )
        return result
    except Exception as e:
        print(f"Error getting ticket {ticket_id}: {e}", file=sys.stderr)
        return {}

def get_last_team_comment_date(ticket_details, team_members):
    """Find the last comment date from a team member"""
    comments = ticket_details.get('comments', [])
    
    last_team_comment = None
    for comment in reversed(comments):  # Start from most recent
        author = comment.get('author', {}).get('username', '').lower()
        if author in team_members:
            comment_date = comment.get('createdDate')
            if comment_date:
                return datetime.fromisoformat(comment_date.replace('Z', '+00:00'))
    
    return None

def days_since_date(date_str):
    """Calculate days since a given date"""
    if not date_str:
        return 0
    
    try:
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return (datetime.now(timezone.utc) - date).days
    except:
        return 0

def is_stale(ticket, team_members):
    """Check if ticket is stale based on severity and last team comment"""
    severity = ticket.get('extensions', {}).get('tt', {}).get('impact')
    
    # Get detailed ticket info for comments
    ticket_details = get_ticket_details(ticket['id'])
    last_team_comment = get_last_team_comment_date(ticket_details, team_members)
    
    # If no team comment, use ticket creation date
    if not last_team_comment:
        created_date = ticket.get('createDate')
        if created_date:
            last_team_comment = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
    
    if not last_team_comment:
        return False, 0
    
    days_since_comment = (datetime.now(timezone.utc) - last_team_comment).days
    
    # Check staleness based on severity
    if severity == 2 or severity == 2.5:  # SEV2
        return days_since_comment > 3, days_since_comment
    elif severity == 3:  # SEV3
        return days_since_comment > 7, days_since_comment
    
    return False, days_since_comment

def main():
    if len(sys.argv) != 2:
        print("Usage: python track_stale_tickets.py <resolver_group_name>", file=sys.stderr)
        sys.exit(1)
    
    group_name = sys.argv[1]
    
    # Get team members
    team_members = get_resolver_group_members(group_name)
    if not team_members:
        print(f"No members found for resolver group: {group_name}", file=sys.stderr)
        sys.exit(1)
    
    # Search for tickets
    tickets = search_tickets(group_name)
    
    stale_tickets = []
    
    for ticket in tickets:
        is_ticket_stale, days_since_comment = is_stale(ticket, team_members)
        
        if is_ticket_stale:
            severity = ticket.get('extensions', {}).get('tt', {}).get('impact', 'Unknown')
            stale_tickets.append([
                ticket['id'],
                ticket.get('title', 'No title'),
                f"SEV_{severity}",
                days_since_comment,
                ticket.get('createDate', 'Unknown'),
                ticket.get('lastUpdatedDate', 'Unknown')
            ])
    
    # Print summary
    print(f"SUMMARY: {len(stale_tickets)} stale tickets for resolver group '{group_name}'", file=sys.stderr)
    
    # Output CSV
    headers = ["Ticket ID", "Title", "Severity", "Days Since Team Comment", "Created Date", "Last Updated"]
    
    writer = csv.writer(sys.stdout)
    writer.writerow(headers)
    writer.writerows(stale_tickets)

if __name__ == "__main__":
    main()