pub mod vci;
pub mod tcbs;

pub use vci::{VciClient, VciError};
pub use tcbs::{TcbsClient, TcbsError};

// Re-export common types
pub use vci::{OhlcvData as VciOhlcvData, CompanyInfo as VciCompanyInfo};
pub use tcbs::{OhlcvData as TcbsOhlcvData, CompanyInfo as TcbsCompanyInfo};

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_module_exports() {
        // Test that we can create clients
        let _vci_client = VciClient::new(false, 6);
        let _tcbs_client = TcbsClient::new(false, 6);
    }
}