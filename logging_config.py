"""
RFC 5424 Compliant Structured Logging for Financial Intelligence MCP Server

This module implements enterprise-grade structured logging with:
- RFC 5424 severity levels (0-7)
- JSON-formatted log records
- Correlation ID tracking for session tracing
- Compliance flags for audit trail
- Separate security-audit file for DENIED operations

Severity Levels (RFC 5424):
  0 - Emergency: System is unusable
  1 - Alert: Action must be taken immediately
  2 - Critical: Critical conditions
  3 - Error: Error conditions
  4 - Warning: Warning conditions
  5 - Notice: Normal but significant condition
  6 - Informational: Informational messages
  7 - Debug: Debug-level messages
"""

import logging
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from pythonjsonlogger import jsonlogger


# ============================================================================
# RFC 5424 SEVERITY LEVELS
# ============================================================================

class RFC5424Severity:
    """RFC 5424 Syslog severity levels"""
    EMERGENCY = 0      # System is unusable
    ALERT = 1          # Action must be taken immediately
    CRITICAL = 2       # Critical conditions
    ERROR = 3          # Error conditions
    WARNING = 4        # Warning conditions
    NOTICE = 5         # Normal but significant condition
    INFORMATIONAL = 6  # Informational messages
    DEBUG = 7          # Debug-level messages

    @classmethod
    def to_python_level(cls, rfc_level: int) -> int:
        """Convert RFC 5424 level to Python logging level"""
        mapping = {
            0: logging.CRITICAL + 10,  # EMERGENCY (higher than CRITICAL)
            1: logging.CRITICAL + 5,   # ALERT (between CRITICAL and ERROR)
            2: logging.CRITICAL,       # CRITICAL
            3: logging.ERROR,          # ERROR
            4: logging.WARNING,        # WARNING
            5: logging.INFO + 5,       # NOTICE (between INFO and WARNING)
            6: logging.INFO,           # INFORMATIONAL
            7: logging.DEBUG,          # DEBUG
        }
        return mapping.get(rfc_level, logging.INFO)


# ============================================================================
# CUSTOM JSON FORMATTER
# ============================================================================

class ComplianceJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter that adds compliance-specific fields.

    Every log record includes:
    - timestamp: ISO 8601 timestamp
    - severity: RFC 5424 severity level (0-7)
    - correlation_id: Session tracking ID
    - compliance_flag: Compliance status indicator
    - message: Log message
    - tool_name: MCP tool being invoked
    - Additional context fields
    """

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add custom fields to log record"""
        super().add_fields(log_record, record, message_dict)

        # Always include timestamp in ISO 8601 format
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'

        # Add RFC 5424 severity level
        log_record['severity'] = getattr(record, 'severity', self._map_level_to_rfc5424(record.levelno))

        # Add correlation ID (set by logger)
        log_record['correlation_id'] = getattr(record, 'correlation_id', 'UNKNOWN')

        # Add compliance flag (set by logger)
        log_record['compliance_flag'] = getattr(record, 'compliance_flag', 'N/A')

        # Add tool name (set by logger)
        log_record['tool_name'] = getattr(record, 'tool_name', 'UNKNOWN')

        # Add service name
        log_record['service'] = 'financial-intelligence-mcp'

        # Add environment (default to production)
        log_record['environment'] = 'production'

    def _map_level_to_rfc5424(self, python_level: int) -> int:
        """Map Python logging level to RFC 5424 severity"""
        if python_level >= logging.CRITICAL + 10:
            return RFC5424Severity.EMERGENCY
        elif python_level >= logging.CRITICAL + 5:
            return RFC5424Severity.ALERT
        elif python_level >= logging.CRITICAL:
            return RFC5424Severity.CRITICAL
        elif python_level >= logging.ERROR:
            return RFC5424Severity.ERROR
        elif python_level >= logging.WARNING:
            return RFC5424Severity.WARNING
        elif python_level >= logging.INFO + 5:
            return RFC5424Severity.NOTICE
        elif python_level >= logging.INFO:
            return RFC5424Severity.INFORMATIONAL
        else:
            return RFC5424Severity.DEBUG


# ============================================================================
# STRUCTURED LOGGER
# ============================================================================

class StructuredLogger:
    """
    Structured logger for MCP server with compliance tracking.

    Features:
    - Automatic correlation ID generation per session
    - RFC 5424 compliant severity levels
    - JSON-formatted logs for machine parsing
    - Separate security audit trail for DENIED operations
    - Contextual logging with tool names and compliance flags
    """

    def __init__(
        self,
        name: str = "financial-intelligence-mcp",
        log_dir: str = "./logs",
        general_log_file: str = "mcp-server.log",
        security_audit_file: str = "security-audit.log"
    ):
        """
        Initialize structured logger.

        Args:
            name: Logger name
            log_dir: Directory for log files
            general_log_file: Filename for general logs
            security_audit_file: Filename for security audit logs
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Create general logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()  # Clear any existing handlers

        # Create security audit logger
        self.security_logger = logging.getLogger(f"{name}.security")
        self.security_logger.setLevel(logging.INFO)
        self.security_logger.handlers.clear()

        # JSON formatter
        formatter = ComplianceJsonFormatter(
            '%(timestamp)s %(severity)s %(correlation_id)s %(compliance_flag)s %(tool_name)s %(message)s'
        )

        # General log file handler
        general_handler = logging.FileHandler(self.log_dir / general_log_file)
        general_handler.setLevel(logging.DEBUG)
        general_handler.setFormatter(formatter)
        self.logger.addHandler(general_handler)

        # Security audit file handler (only for DENIED compliance attempts)
        security_handler = logging.FileHandler(self.log_dir / security_audit_file)
        security_handler.setLevel(logging.WARNING)
        security_handler.setFormatter(formatter)
        self.security_logger.addHandler(security_handler)

        # Console handler for development (optional)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Correlation ID for session tracking
        self.correlation_id: Optional[str] = None

    def generate_correlation_id(self) -> str:
        """Generate new correlation ID for session tracking"""
        self.correlation_id = str(uuid.uuid4())
        return self.correlation_id

    def set_correlation_id(self, correlation_id: str) -> None:
        """Set correlation ID for session tracking"""
        self.correlation_id = correlation_id

    def _log(
        self,
        level: int,
        message: str,
        tool_name: str,
        compliance_flag: str,
        rfc_severity: int,
        extra_fields: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Internal logging method with compliance context.

        Args:
            level: Python logging level
            message: Log message
            tool_name: Name of MCP tool being invoked
            compliance_flag: Compliance status (APPROVED, DENIED, PENDING, N/A)
            rfc_severity: RFC 5424 severity level (0-7)
            extra_fields: Additional context fields
        """
        extra = {
            'correlation_id': self.correlation_id or 'UNKNOWN',
            'tool_name': tool_name,
            'compliance_flag': compliance_flag,
            'severity': rfc_severity
        }

        if extra_fields:
            extra.update(extra_fields)

        self.logger.log(level, message, extra=extra)

    def log_tool_invocation(
        self,
        tool_name: str,
        input_params: Dict[str, Any],
        compliance_flag: str = "N/A"
    ) -> None:
        """
        Log MCP tool invocation.

        Args:
            tool_name: Name of tool being called
            input_params: Tool input parameters
            compliance_flag: Compliance status
        """
        self._log(
            level=logging.INFO,
            message=f"Tool invoked: {tool_name}",
            tool_name=tool_name,
            compliance_flag=compliance_flag,
            rfc_severity=RFC5424Severity.INFORMATIONAL,
            extra_fields={
                'event_type': 'tool_invocation',
                'input_params': input_params
            }
        )

    def log_tool_success(
        self,
        tool_name: str,
        compliance_flag: str = "N/A",
        result_summary: Optional[str] = None
    ) -> None:
        """
        Log successful tool execution.

        Args:
            tool_name: Name of tool
            compliance_flag: Compliance status
            result_summary: Brief summary of result
        """
        extra = {'event_type': 'tool_success'}
        if result_summary:
            extra['result_summary'] = result_summary

        self._log(
            level=logging.INFO,
            message=f"Tool completed successfully: {tool_name}",
            tool_name=tool_name,
            compliance_flag=compliance_flag,
            rfc_severity=RFC5424Severity.INFORMATIONAL,
            extra_fields=extra
        )

    def log_compliance_approved(
        self,
        tool_name: str,
        ticker: str,
        reason: str
    ) -> None:
        """
        Log compliance approval.

        Args:
            tool_name: Name of tool
            ticker: Entity ticker
            reason: Approval reason
        """
        self._log(
            level=logging.INFO,
            message=f"Compliance APPROVED for {ticker}: {reason}",
            tool_name=tool_name,
            compliance_flag="APPROVED",
            rfc_severity=RFC5424Severity.NOTICE,
            extra_fields={
                'event_type': 'compliance_check',
                'compliance_decision': 'APPROVED',
                'ticker': ticker,
                'reason': reason
            }
        )

    def log_compliance_denied(
        self,
        tool_name: str,
        ticker: str,
        reason: str
    ) -> None:
        """
        Log compliance denial - CRITICAL SECURITY EVENT.

        This is logged to both general log and security audit log.

        Args:
            tool_name: Name of tool
            ticker: Entity ticker
            reason: Denial reason
        """
        extra = {
            'event_type': 'compliance_check',
            'compliance_decision': 'DENIED',
            'ticker': ticker,
            'reason': reason,
            'security_alert': True
        }

        # Log to general log
        self._log(
            level=logging.WARNING,
            message=f"Compliance DENIED for {ticker}: {reason}",
            tool_name=tool_name,
            compliance_flag="DENIED",
            rfc_severity=RFC5424Severity.WARNING,
            extra_fields=extra
        )

        # Log to security audit log
        security_extra = {
            'correlation_id': self.correlation_id or 'UNKNOWN',
            'tool_name': tool_name,
            'compliance_flag': 'DENIED',
            'severity': RFC5424Severity.WARNING,
            **extra
        }
        self.security_logger.warning(
            f"SECURITY AUDIT: Compliance DENIED for {ticker}: {reason}",
            extra=security_extra
        )

    def log_data_retrieval_error(
        self,
        tool_name: str,
        ticker: str,
        error_code: str,
        error_message: str
    ) -> None:
        """
        Log data retrieval error.

        Args:
            tool_name: Name of tool
            ticker: Entity ticker
            error_code: Error code
            error_message: Error message
        """
        self._log(
            level=logging.ERROR,
            message=f"Data retrieval error for {ticker}: {error_message}",
            tool_name=tool_name,
            compliance_flag="N/A",
            rfc_severity=RFC5424Severity.ERROR,
            extra_fields={
                'event_type': 'data_retrieval_error',
                'ticker': ticker,
                'error_code': error_code,
                'error_message': error_message
            }
        )

    def log_silent_failure_detected(
        self,
        tool_name: str,
        ticker: str,
        failure_type: str,
        detail: str
    ) -> None:
        """
        Log silent failure detection (API throttle, insufficient data, etc).

        Args:
            tool_name: Name of tool
            ticker: Entity ticker
            failure_type: Type of silent failure
            detail: Detailed explanation
        """
        self._log(
            level=logging.WARNING,
            message=f"Silent failure detected for {ticker}: {failure_type}",
            tool_name=tool_name,
            compliance_flag="N/A",
            rfc_severity=RFC5424Severity.WARNING,
            extra_fields={
                'event_type': 'silent_failure_detection',
                'ticker': ticker,
                'failure_type': failure_type,
                'detail': detail
            }
        )


# ============================================================================
# GLOBAL LOGGER INSTANCE
# ============================================================================

# Create global logger instance
structured_logger = StructuredLogger()

# Export for use in other modules
__all__ = [
    'RFC5424Severity',
    'StructuredLogger',
    'structured_logger'
]
