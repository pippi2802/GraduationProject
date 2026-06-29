package edu.penn.rtg.csa.dmpr;

import java.io.BufferedWriter;
import java.io.FileWriter;
import java.io.IOException;
import java.text.DecimalFormat;

import edu.penn.rtg.common.Tool;

public class XMLWriter4DMPR {
	
	private String outputFilename;
	private BufferedWriter outputFile;
	private String resultString; 
	private Component rootComponent;
	private DecimalFormat df;
	
	public XMLWriter4DMPR(String outputFilename, Component rootComponent){
		try{
			this.rootComponent = rootComponent;
			this.outputFilename = outputFilename;
			outputFile = new BufferedWriter(new FileWriter(outputFilename));
			resultString = "";
			df = new DecimalFormat("#.##");
			System.out.println("Open the file " + outputFilename + " to write...");
		}catch(IOException e){
			System.err.println(e.getMessage());
			e.printStackTrace();
		}
		
	}
	
	public void writeComponentInterfaceTree(){
		try{
			this.writeComponentInterface(this.rootComponent);
			Tool.debug(resultString);
			outputFile.write(resultString);
			outputFile.flush();
			outputFile.close();
		}catch (IOException e){
			System.err.println(e.getMessage());
			e.printStackTrace();
		}
		
	}
	
	/**
	 * Function writeComponentInterface
	 * Recursively write the component tree into xml file.
	 * We print out hte interface as (Pi_hybrid, Theta_hybrid, m_prime_hybrid) to make it consistant with Insik's interface. 
	 * @param component
	 */
	private void writeComponentInterface(Component component){
		//We print out the interface as (Pi_hybrid, Theta_hybrid, m_prime_hybrid) to make it consistant with Insik's interface. 
		//Actually, this interface implicitly indicate Pi_hybrid-1 dedicated cores because it fix the interface transformation
		int m_prime_hybrid = component.getCacheAwareMPRInterface().getM_prime() + component.getCacheAwareMPRInterface().getM_dedicatedCores();
		double Theta_hybrid = component.getCacheAwareMPRInterface().getTheta() + component.getCacheAwareMPRInterface().getPi()*component.getCacheAwareMPRInterface().getM_dedicatedCores();
		double Pi_hybrid = component.getCacheAwareMPRInterface().getPi();
		resultString = resultString + "<component name=\"" + component.getComponentName() + "\" resource_model=\"DMPR model\" >\r\n" +
					"<resource>\r\n" +
						"<model cpus=\"" + m_prime_hybrid + "\" period=\"" + df.format(Pi_hybrid) + "\" execution_time=\"" + df.format(Theta_hybrid) + "\"> </model> \r\n" +
					"</resource> \r\n"; 
		//print out the interface tasks by iteration.
		resultString += "<processed_task> \r\n";
		for(int i=0; !component.getInterfaceTaskset().isEmpty() && i<component.getInterfaceTaskset().size();i++){
			Task currentTask = component.getInterfaceTaskset().get(i);
			resultString += "<model period=\"" + df.format(currentTask.getPeriod()) + "\" execution_time=\"" + 
						df.format(currentTask.getExe()) + "\" deadline=\"" + df.format(currentTask.getDeadline()) + "\" > </model> \r\n";
		}
		resultString += "</processed_task> \r\n";
		//recursively print out the child components' interface
		for(int i=0; i<component.getChildComponents().size(); i++){
			writeComponentInterface(component.getChildComponents().get(i));
		}
		resultString += "</component>\r\n";		
	}
	
	public void writeOriginalComponentTree() throws IOException{
		this.writeOriginalComponent(this.rootComponent);
		Tool.debug(resultString);
		outputFile.write(resultString);
		outputFile.flush();
		outputFile.close();
	}
	
	private void writeOriginalComponent(Component component) {
		resultString = resultString + "< component name="+component.getComponentName() + 
				"  scheduling=" + component.getSchedulingPolicy() + "  period=" + component.getCacheAwareMPRInterface().getPi() + " > \r\n"; 
		for(int i=0; i<component.getChildComponents().size(); i++){
			writeOriginalComponent(component.getChildComponents().get(i));
		}
		for(int i=0; i<component.getTaskset().size(); i++){
			Task task = component.getTaskset().get(i);
			this.writeOriginalTask(task);
		}
		
		resultString = resultString + "</component> \r\n" ;	

	}
	
	private void writeOriginalTask(Task task){
		resultString = resultString + "< task name=" + task.getName() + " p=" + task.getPeriod() + 
				" d=" + task.getDeadline() + " e=" + task.getExe() + " delta_rel=" + task.getDelta_rel() +
				" delta_sch=" + task.getDelta_sch() + " delta_cxs=" + task.getDelta_cxs() + 
				" delta_crpmd=" + task.getDelta_crpmd() + "/> \r\n"; 
	}
 
	/**
	 * @param args
	 * @throws IOException 
	 */
	public static void main(String[] args) {
		// TODO Auto-generated method stub
		try{
			XMLInterpreter4DMPR xmlInputParse = new XMLInterpreter4DMPR("CAMPR-input.xml");		
			xmlInputParse.parseFile();
			Component rootComponent = xmlInputParse.getRootComponent();
			XMLWriter4DMPR xmlOutputOriginalComponentTree = new XMLWriter4DMPR("CAMPR-component-output.xml", rootComponent);
			XMLWriter4DMPR xmlOutputInterfaceTree = new XMLWriter4DMPR("CAMPR-interface-output.xml", rootComponent);
			
			xmlOutputOriginalComponentTree.writeOriginalComponentTree();
			xmlOutputInterfaceTree.writeComponentInterfaceTree();
		}catch (Exception e){
			System.err.println(e.getMessage());
			e.printStackTrace();
		}
		
		

	}

}
